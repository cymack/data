#!/bin/bash

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

#######################################
# Download latest data for all pipelines and publish outputs to GCS prod bucket
#######################################

# This is brittle but prevents from continuing in case of failure since we don't want to overwrite
# files in the server if anything went wrong
set -xe

# Delete ourselves after a two hour timeout
export NAME=$(curl -X GET http://metadata.google.internal/computeMetadata/v1/instance/name -H 'Metadata-Flavor: Google')
export ZONE=$(curl -X GET http://metadata.google.internal/computeMetadata/v1/instance/zone -H 'Metadata-Flavor: Google')
$(sleep 7200s && gcloud --quiet compute instances delete $NAME --zone=$ZONE)&

# Declare the branch to use to run code
readonly BRANCH=appengine

# Install dependencies using the package manager
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -yq && sudo apt-get install -yq git wget curl

function install_python {
    sudo apt-get install -y make build-essential libssl-dev zlib1g-dev libbz2-dev \
        libreadline-dev libsqlite3-dev llvm libncurses5-dev libncursesw5-dev xz-utils \
        tk-dev libffi-dev liblzma-dev python-openssl
    git clone https://github.com/pyenv/pyenv.git ~/.pyenv
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"
    pyenv install 3.8.3
    pyenv global 3.8.3
}

# Clone the repo into a temporary directory
readonly TMPDIR=$(mktemp -d -t opencovid-$(date +%Y-%m-%d-%H-%M-%S)-XXXX)
git clone https://github.com/open-covid-19/data.git --single-branch -b $BRANCH "$TMPDIR/opencovid"

# Install Python and its dependencies
install_python
python3.8 -m pip install -r "$TMPDIR/opencovid/src/requirements.txt"

# Run the update command
python3.8 "$TMPDIR/opencovid/src/appengine.py" --command publish
