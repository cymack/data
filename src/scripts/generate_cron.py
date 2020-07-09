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

"""
This script creates the cron.yaml configuration needed to automatically update
all the data pipelines using appengine. To generate the configuration and
upload it to a deployed appengine application, run the following commands from
the `src` folder, which already has an app.yaml config file:
```sh
python ./scripts/generate_cron.py > cron.yaml
gcloud app deploy cron.yaml
```
"""

import os
import sys
import copy
from typing import Iterator, Dict
import yaml

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# pylint: disable=wrong-import-position
from lib.pipeline_tools import get_pipelines


def get_cron_jobs() -> Iterator[Dict]:
    """ Iterator of cron job configurations """

    # Apply sensible retry parameters for all cron jobs
    retry_params = {"retry_parameters": {"min_backoff_seconds": 60, "max_doublings": 5}}

    # Define the schedules and reuse them across all tasks
    sched_hourly = {"schedule": "every 1 hours"}

    for data_pipeline in get_pipelines():
        # The job that combines data sources into a table runs hourly
        yield {
            "url": f"/combine?table={data_pipeline.table}",
            **copy.deepcopy(sched_hourly),
            **copy.deepcopy(retry_params),
        }

        for idx, _ in enumerate(data_pipeline.data_sources):
            # The job to pull each individual data source runs hourly
            yield {
                "url": f"/update?table={data_pipeline.table}&idx={idx}",
                **copy.deepcopy(sched_hourly),
                **copy.deepcopy(retry_params),
            }


if __name__ == "__main__":
    yaml.dump({"cron": list(get_cron_jobs())}, sys.stdout)
