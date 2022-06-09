import csv
import dataclasses
import datetime
import json
import pathlib
import typing
import urllib.parse
import urllib.request
import zipfile

from icecream import ic
from rich import inspect as rinspect
from rich import print as rprint

JSON_SUFFIX = ".json"
JSON_GLOB = f"*{JSON_SUFFIX}"

BIOGUIDE_URL = "https://bioguide.congress.gov/bioguide/data/BioguideProfiles.zip"
BIOGUIDE_ZIP_NAME = urllib.parse.urlparse(BIOGUIDE_URL).path.split("/")[-1]
BIOGUIDE_ZIP_PATH = pathlib.Path(BIOGUIDE_ZIP_NAME)
BIOGUIDE_DIR_PATH = BIOGUIDE_ZIP_PATH.with_suffix("")

CSV_OUTPUT_PATH = pathlib.Path("bioguide_profiles.csv")


@dataclasses.dataclass
class Field:
    path: list[str]
    label: str


PROFILE_FIELDS = [
    Field(["familyName"], "Family Name"),
    Field(["givenName"], "Given Name"),
    Field(["birthCirca"], "Birth Circa"),
    Field(["deathCirca"], "Death Circa"),
]
BIRTH_DATE_INDEX = len(PROFILE_FIELDS)
PROFILE_FIELDS.append(Field(["birthDate"], "Birth Date"))
DEATH_DATE_INDEX = len(PROFILE_FIELDS)
PROFILE_FIELDS.append(Field(["deathDate"], "Death Date"))

JOB_FIELDS = [
    Field(["job", "name"], "Job Name"),
    Field(["startDate"], "Job Start Date"),
    Field(["startCirca"], "Job Start Circa"),
    Field(["congressAffiliation", "congress", "congressNumber"], "Congress Number"),
]
CONGRESS_START_DATE_INDEX = len(JOB_FIELDS)
JOB_FIELDS.append(
    Field(["congressAffiliation", "congress", "startDate"], "Congress Start Date")
)

COMPUTED_FIELDS = []
AGE_AT_DEATH_INDEX = len(COMPUTED_FIELDS)
COMPUTED_FIELDS.append(Field([], "Age at Death"))
AGE_AT_CONGRESS_START_INDEX = len(COMPUTED_FIELDS)
COMPUTED_FIELDS.append(Field([], "Age at Congress Start"))

ALL_FIELDS = PROFILE_FIELDS + JOB_FIELDS + COMPUTED_FIELDS


def glob_bioguide_json_profiles() -> typing.Generator[pathlib.Path, None, None]:
    return BIOGUIDE_DIR_PATH.glob(JSON_GLOB)


def obtain_bioguide_profiles() -> None:
    BIOGUIDE_DIR_PATH.mkdir(parents=True, exist_ok=True)
    if not next(glob_bioguide_json_profiles(), None):
        if not BIOGUIDE_ZIP_PATH.exists():
            urllib.request.urlretrieve(
                BIOGUIDE_URL,
                BIOGUIDE_ZIP_PATH,
            )
        with zipfile.ZipFile(BIOGUIDE_ZIP_PATH) as zf:
            curdirpath = pathlib.Path()
            json_suffixes = [".json"]
            safe_json_members = [
                n
                for n in zf.namelist()
                if (p := pathlib.Path(n)).parent == curdirpath
                and p.suffixes == json_suffixes
            ]
            zf.extractall(BIOGUIDE_DIR_PATH, safe_json_members)


def coerce_to_date(value: str) -> datetime.date:
    if not isinstance(value, str):
        raise ValueError("expected str value", value)
    for datestr in [value, f"{value}-01", f"{value}-01-01"]:
        try:
            return datetime.date.fromisoformat(datestr)
        except ValueError:
            ...
    raise ValueError("expected one of YYYY-MM-DD, YYYY-MM, YYYY", value)


def coerce_to_year(value: str) -> int:
    if not isinstance(value, str):
        raise ValueError("expected str value", value)
    for datestr in [value, f"{value}-01", f"{value}-01-01"]:
        try:
            return datetime.date.fromisoformat(datestr).year
        except ValueError:
            ...
    raise ValueError("expected one of YYYY-MM-DD, YYYY-MM, YYYY", value)


def resolve(path: list[str], data: dict) -> typing.Any:
    keys = list(path)
    node = data
    key = None
    while keys and isinstance(node, dict):
        key = keys.pop(0)
        if key in node:
            node = node[key]
        else:
            return False
    if isinstance(node, dict):
        raise KeyError("path does not resolve to leaf value", path, data)
    if keys:
        raise KeyError("incomplete path", path, data)
    if node is None:
        return False
    return node


def age_or_false(birth_date, measure_date):
    try:
        return coerce_to_year(measure_date) - coerce_to_year(birth_date)
    except ValueError:
        return False


def convert_bioguide_profiles_to_politician_ages_csv():
    with open(CSV_OUTPUT_PATH, "w") as outcsv:
        out = csv.writer(outcsv)
        out.writerow([f.label for f in ALL_FIELDS])
        profile_count = 0
        job_count = 0
        for profile_path in glob_bioguide_json_profiles():
            with open(profile_path) as profile_file:
                profile = json.load(profile_file)
            profile_count += 1
            profile_values = [resolve(pf.path, profile) for pf in PROFILE_FIELDS]
            computed_values = [False] * len(COMPUTED_FIELDS)
            birth_date = profile_values[BIRTH_DATE_INDEX]
            death_date = profile_values[DEATH_DATE_INDEX]
            computed_values[AGE_AT_DEATH_INDEX] = age_or_false(birth_date, death_date)
            jobs = resolve(["jobPositions"], profile)
            if isinstance(jobs, list):
                for job in jobs:
                    job_count += 1
                    job_values = [resolve(jf.path, job) for jf in JOB_FIELDS]
                    congress_start_date = job_values[CONGRESS_START_DATE_INDEX]
                    computed_values[AGE_AT_CONGRESS_START_INDEX] = age_or_false(
                        birth_date, congress_start_date
                    )
                    out.writerow(profile_values + job_values + computed_values)
    print("profiles:", profile_count)
    print("jobs:    ", job_count)


def main():
    obtain_bioguide_profiles()
    convert_bioguide_profiles_to_politician_ages_csv()


if __name__ == "__main__":
    main()
