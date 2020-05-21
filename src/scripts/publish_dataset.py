#!/usr/bin/env python

import re
import os
import sys
import shutil
import datetime
from pandas import DataFrame

# This script must be run from /src
sys.path.append(os.getcwd())
from lib.io import read_file, export_csv
from lib.utils import ROOT

from backcompat_forecast import main as build_forecast


def snake_to_camel_case(txt: str) -> str:
    """ Used to convert V2 column names to V1 column names for backwards compatibility """
    txt = re.sub(r"_(\w)", lambda m: m.group(1).upper(), txt.capitalize())


def subset_last_days(data: DataFrame, days: int) -> DataFrame:
    """ Used to get the last N days of data """
    # Early exit: this data has no date
    if not "date" in data.columns or len(data.date.dropna()) == 0:
        return data
    else:
        last_date = datetime.date.fromisoformat(data.date.max())
        first_date = last_date - datetime.timedelta(days=days)
        return data[data.date > first_date.isoformat()]


# Create the folder which will be published
v2_folder = ROOT / "public" / "v2"
v2_folder.mkdir(exist_ok=True, parents=True)

# Copy all output files to the V2 folder
print("Copying files to output folder...")
for output_file in (ROOT / "output").glob("*.csv"):
    shutil.copy(output_file, v2_folder / output_file.name)

# Merge all output files into a single data.csv file
print("Creating master table...")
all_data = read_file(v2_folder / "index.csv")
for output_file in v2_folder.glob("*.csv"):
    if output_file.name not in ("index.csv", "master.csv"):
        all_data = all_data.merge(read_file(output_file), how="left")

# Drop rows without a single dated record
export_csv(all_data.dropna(subset=["date"]), v2_folder / "master.csv")

# Create subsets with the last 30, 14, 7 and 1 last days of data
print("Creating last N days subsets...")
for n_days in (30, 14, 7, 1):
    n_days_folder = v2_folder / str(n_days)
    n_days_folder.mkdir(exist_ok=True)
    for csv_file in (v2_folder).glob("*.csv"):
        data = read_file(csv_file, low_memory=False)
        export_csv(subset_last_days(data, n_days), n_days_folder / csv_file.name)

# Convert all CSV files to JSON using values format
print("Converting CSV to JSON...")
for csv_file in (v2_folder).glob("**/*.csv"):
    data = read_file(csv_file, low_memory=False)
    json_path = str(csv_file).replace("csv", "json")
    data.to_json(json_path, orient="values")

# Perform data transformations for backwards compatibility
v1_folder = ROOT / "public"
print("Performing backwards compatibility transformations...")

# Create the legacy data.csv file
data = read_file(v2_folder / "index.csv")
data = data.merge(read_file(v2_folder / "geography.csv"))
data = data.merge(read_file(v2_folder / "demographics.csv"))
data = data.merge(read_file(v2_folder / "epidemiology.csv"))
data = data[data.subregion2_code.isna()]
rename_columns = {
    "date": "Date",
    "key": "Key",
    "country_code": "CountryCode",
    "country_name": "CountryName",
    "subregion1_code": "RegionCode",
    "subregion1_name": "RegionName",
    "total_confirmed": "Confirmed",
    "total_deceased": "Deaths",
    "latitude": "Latitude",
    "longitude": "Longitude",
    "population": "Population",
}
data = data[rename_columns.keys()].rename(columns=rename_columns)
data = data.dropna(subset=["Confirmed", "Deaths"], how="all")
data = data.sort_values(["Date", "Key"])
export_csv(data, v1_folder / "data.csv")

# Create the v1 minimal.csv file
export_csv(data[["Date", "Key", "Confirmed", "Deaths"]], v1_folder / "data_minimal.csv")

# Create the v1 weather.csv file
weather = read_file(v2_folder / "weather.csv")
weather.columns = list(map(snake_to_camel_case, weather.columns))
weather = weather.rename(columns={"noaa_distance": "distance", "noaa_station": "station"})
export_csv(weather, v1_folder / "weather.csv")

# Create the v1 mobility.csv file
export_csv(
    read_file("https://open-covid-19.github.io/data/mobility.csv"), v1_folder / "mobility.csv",
)

# Create the v1 forecast.csv file
# export_csv(build_forecast(), v1_folder / "forecast.csv")

# Create the v1 CSV files which only require column mapping
v1_v2_name_map = {"response": "oxford-government-response"}
for v1_name, v2_name in v1_v2_name_map.items():
    df = read_file(v2_folder / f"{v2_name}.csv")
    df.columns = list(map(snake_to_camel_case, df.columns))
    export_csv(df, v1_folder / f"{v1_name}.csv")

# Convert all v1 CSV files to JSON using record format
for csv_file in (v1_folder).glob("*.csv"):
    data = read_file(csv_file, low_memory=False)
    json_path = str(csv_file).replace("csv", "json")
    data.to_json(json_path, orient="records")