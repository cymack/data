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

import os
from pathlib import Path

SRC = Path(os.path.dirname(__file__)) / ".."
URL_OUTPUTS_PROD = "https://storage.googleapis.com/covid19-open-data/v2"
CACHE_URL = "https://raw.githubusercontent.com/open-covid-19/data/cache"
APP_ENGINE_URL = "https://github-open-covid-19.ue.r.appspot.com"
