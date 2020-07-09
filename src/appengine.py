#!/usr/bin/env python
# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import os.path
from pathlib import Path
from functools import partial
from tempfile import TemporaryDirectory
from typing import Iterator

from flask import Flask, request
from google.cloud import storage
from google.oauth2.credentials import Credentials
from google.cloud.storage.blob import Blob

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# pylint: disable=wrong-import-position
from lib.cast import safe_int_cast
from lib.concurrent import thread_map
from lib.io import export_csv
from lib.pipeline import DataPipeline
from lib.utils import SRC

app = Flask(__name__)
BLOB_OP_MAX_RETRIES = 3
DEFAULT_BUCKET_NAME = "open-covid-data"


def get_storage_client():
    """
    Creates an instance of google.cloud.storage.Client using a token if provided, otherwise
    the default credentials are used.
    """
    token_env_key = "GCP_TOKEN"
    if os.getenv(token_env_key) is None:
        return storage.Client()
    else:
        credentials = Credentials(os.getenv(token_env_key))
        return storage.Client(credentials=credentials)


def get_storage_bucket(bucket_name: str = DEFAULT_BUCKET_NAME):
    client = get_storage_client()

    # If bucket name is not provided, read it from env var
    bucket_env_key = "GCS_BUCKET_NAME"
    bucket_name = bucket_name or os.getenv(bucket_env_key)
    assert bucket_name is not None, f"{bucket_env_key} not set"
    return client.get_bucket(bucket_name)


def download_folder(remote_path: str, local_folder: Path) -> None:
    bucket = get_storage_bucket()

    def _download_blob(local_folder: Path, blob: Blob) -> None:
        # Remove the prefix from the remote path
        rel_path = blob.name.split(f"{remote_path}/", 2)[-1]
        print(f"Downloading {rel_path} to {local_folder}/")
        file_path = local_folder / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(BLOB_OP_MAX_RETRIES):
            try:
                return blob.download_to_filename(file_path)
            except Exception as exc:
                print(exc, file=sys.stderr)

    map_func = partial(_download_blob, local_folder)
    thread_map(map_func, bucket.list_blobs(prefix=remote_path), total=None, disable=True)


def upload_folder(remote_path: str, local_folder: Path) -> None:
    bucket = get_storage_bucket()

    def _upload_file(remote_path: str, file_path: Path):
        print(f"Uploading {file_path} to {remote_path}/")
        target_path = file_path.relative_to(local_folder)
        blob = bucket.blob(os.path.join(remote_path, target_path))
        for _ in range(BLOB_OP_MAX_RETRIES):
            try:
                return blob.upload_from_filename(file_path)
            except Exception as exc:
                print(exc, file=sys.stderr)

    map_func = partial(_upload_file, remote_path)
    thread_map(map_func, local_folder.glob("**/*"), total=None, disable=True)


def get_table_names() -> Iterator[str]:
    for item in (SRC / "pipelines").iterdir():
        if not item.name.startswith("_") and not item.is_file():
            yield item.name.replace("_", "-")


@app.route("/update")
def update() -> None:
    table_name = request.args.get("table")
    data_source_idx = safe_int_cast(request.args.get("idx"))
    assert table_name in list(get_table_names())
    with TemporaryDirectory() as output_folder:
        output_folder = Path(output_folder)
        (output_folder / "snapshot").mkdir(parents=True, exist_ok=True)
        (output_folder / "intermediate").mkdir(parents=True, exist_ok=True)

        # Load the pipeline configuration given its name
        pipeline_name = table_name.replace("-", "_")
        data_pipeline = DataPipeline.load(pipeline_name)

        # Limit the sources to only the index provided
        if data_source_idx is not None:
            data_pipeline.data_sources = [data_pipeline.data_sources[data_source_idx]]

        # Produce the intermediate files from the data source
        intermediate_results = data_pipeline.parse(output_folder, process_count=1)
        data_pipeline._save_intermediate_results(
            output_folder / "intermediate", intermediate_results
        )

        # Upload results
        upload_folder("snapshot", output_folder / "snapshot")
        upload_folder("intermediate", output_folder / "intermediate")

    return "OK"


@app.route("/combine")
def combine() -> None:
    table_name = request.args.get("table")
    assert table_name in list(get_table_names())
    with TemporaryDirectory() as output_folder:
        output_folder = Path(output_folder)
        (output_folder / "tables").mkdir(parents=True, exist_ok=True)

        # Download all the intermediate files
        download_folder("intermediate", output_folder / "intermediate")

        # Load the pipeline configuration given its name
        pipeline_name = table_name.replace("-", "_")
        data_pipeline = DataPipeline.load(pipeline_name)

        # Re-load all intermediate results
        intermediate_results = data_pipeline._load_intermediate_results(
            output_folder / "intermediate", data_pipeline.data_sources
        )

        # Combine all intermediate results into a single dataframe
        pipeline_output = data_pipeline.combine(intermediate_results)

        # Output combined data to disk
        export_csv(pipeline_output, output_folder / "tables" / f"{table_name}.csv")

        # Upload results
        upload_folder("v2", output_folder / "tables")

    return "OK"


if __name__ == "__main__":

    # Only for debugging purposes
    app.run(host="127.0.0.1", port=8080, debug=True)
