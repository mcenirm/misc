import collections
import configparser
import csv
import datetime
import logging
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any, List, Mapping, Tuple

CHECK_FALCON_REPORTS_SETTINGS_ATTRIBUTE_NAMES = ["access_log", "date_expression"]
CHECK_FALCON_REPORTS_SETTINGS_SECTION_NAME = "settings"


class CheckFalconReportsSettings:
    access_log: Path
    date_expression: str = "yesterday"

    def __init__(self, name="check_falcon_reports", argv=[]):
        self._name = name
        config = configparser.ConfigParser()
        files = guess_config_files(name)
        logging.debug("files: " + repr(files))
        config.read(files)
        logging.debug(
            "from files: "
            + str(dict(config[CHECK_FALCON_REPORTS_SETTINGS_SECTION_NAME]))
        )
        args, kwargs = config_from_argv(argv)
        logging.debug("from argv: " + str(args) + " " + str(kwargs))
        combined = {**config[CHECK_FALCON_REPORTS_SETTINGS_SECTION_NAME], **kwargs}
        for attrname in CHECK_FALCON_REPORTS_SETTINGS_ATTRIBUTE_NAMES:
            if attrname in combined:
                setattr(self, attrname, combined[attrname])
        if args:
            self.date_expression = args[0]
        for attrname in CHECK_FALCON_REPORTS_SETTINGS_ATTRIBUTE_NAMES:
            value = getattr(self, attrname)
            logging.debug(attrname + ": " + str(value))


class Record(dict):
    FIELD_LABELS = collections.OrderedDict(
        result="Result",
        computer="Computer",
        ip="IP",
        user="User",
        date="Date",
        time="Time",
        zone="Zone",
        psbuild="PSBuild",
        tagged="Tagged?",
        tag="Tag",
        model="Model",
        osversion="OS",
        serial="Serial",
    )


def main():
    # logging.basicConfig(level=logging.DEBUG)
    settings = CheckFalconReportsSettings(argv=sys.argv)
    return run(settings)


def run(
    settings: CheckFalconReportsSettings,
    out=sys.stdout,
    err=sys.stderr,
) -> int:
    date_filter = determine_date_filter(settings.date_expression)
    today = datetime.date.today()
    previous_log, current_log = determine_log_filenames(settings.access_log, today)

    all_lines = []
    unparsed_lines = []
    parsed_lines = []
    date_filter_lines = []
    matched_lines = []
    records = []
    for line in cat(previous_log, current_log):
        all_lines.append(line)
        d = parse(line)
        if d:
            parsed_lines.append(d)
            if d["t"].startswith(date_filter):
                date_filter_lines.append(d)
                if d["r"].lower().startswith("get /falcon-report.txt?"):
                    matched_lines.append(d)

                    t_date, t_time = d["t"].split(":", 1)
                    t_time, t_zone = t_time.split(None, 1)
                    t_zone = apostrophize_number_as_text(t_zone)

                    lead, psbuild = d["user_agent"].rsplit("/", 1)
                    psbuild = apostrophize_number_as_text(psbuild)
                    if not lead.lower().endswith("powershell"):
                        psbuild = "n/a"

                    record = Record(
                        ip=d["h"],
                        user=d["u"],
                        date=t_date,
                        time=t_time,
                        zone=t_zone,
                        psbuild=psbuild,
                        tagged="untagged",
                    )

                    method, rest = d["r"].split(None, 1)
                    path, rest = rest.rsplit(None, 1)
                    query = urllib.parse.urlparse(path, "http").query
                    data = urllib.parse.parse_qs(query)

                    for k in data.keys():
                        v = data[k][0]
                        if k == "tag":
                            record["tagged"] = "tagged"
                        elif k == "computer" and "." in v:
                            v = v.split(".")[0]
                        record[k] = apostrophize_number_as_text(v)
                        if not k in Record.FIELD_LABELS:
                            print("** unexpected parameter:", k, file=err)
                            Record.FIELD_LABELS[k] = k

                    records.append(record)
        else:
            unparsed_lines.append(line)
    if unparsed_lines:
        print(unparsed_lines[0], file=err)
        return 1
    if matched_lines:
        writer = csv.DictWriter(out, Record.FIELD_LABELS.keys(), restval="n/a")
        writer.writerow(Record.FIELD_LABELS)
        writer.writerows(records)
    return 0


def config_from_argv(argv: List[str]) -> Tuple[List[str], Mapping[str, Any]]:
    argv = argv[1:]
    kwargs = {}
    args = []
    while argv:
        arg = argv.pop(0)
        if arg == "--":
            args = argv
            break
        if arg.startswith("-"):
            arg = arg.lstrip("-")
            if arg.startswith("no-"):
                name = arg[3:]
                value = False
            elif "=" in arg:
                name, value = arg.split("=", 1)
            else:
                value = True
            name = name.replace("-", "_")
            kwargs[name] = value
        else:
            args.append(arg)
    return args, kwargs


def guess_config_files(app_name: str) -> List[str]:
    config_base = os.environ.get("XDG_CONFIG_HOME", os.environ["HOME"] + "/.config")
    suffix = ("_" if "_" in app_name else "") + "config"
    guesses = list(
        filter(
            bool,
            [
                os.environ.get(app_name.upper() + "_CONFIG"),
                "/".join((config_base, app_name, "config")),
                os.environ["HOME"] + "/." + app_name + suffix,
            ],
        )
    )
    return guesses


# data_dir:   .local/share/{{NAME}}
# config_dir: .config/{{NAME}}
# cache_dir:  .cache/{{NAME}}
# state_dir:  .local/state/{{NAME}}
# log_dir:    .cache/{{NAME}}/log


def determine_defaults():
    config_file = find_config_file()
    config = load_config_from_file(config_file)
    date_expression = config.get("date_expression", "yesterday")
    access_log = config["access_log"]
    return date_expression, access_log


def load_config_from_file(config_file):
    config = {}
    with open(config_file) as f:
        lines = f.readlines()
    for line in lines:
        line = str(line).strip()
        if not line or line.startswith("#"):
            continue
        try:
            name, value = line.split(":", 1)
        except ValueError:
            continue
        name = name.strip()
        value = value.strip()
        config[name] = value
    return config


def find_config_file(app_name="falcon_reports"):
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if not config_home:
        config_home = os.environ["HOME"] + "/.config"
    config_file = config_home + "/" + app_name + ".cfg"
    return config_file


def find_gnu_date():
    gdate = [_ for _ in ["gdate", "date"] if shutil.which(_)][0]
    return gdate


def determine_date_filter(date_expression):
    gdate = find_gnu_date()
    date_filter = (
        subprocess.Popen(
            [
                gdate,
                "-d",
                date_expression,
                "+%d/%b/%Y",
            ],
            stdout=subprocess.PIPE,
            universal_newlines=True,
        )
        .communicate()[0]
        .strip()
    )
    return date_filter


def determine_log_filenames(access_log, today):
    previous_log = access_log + "-" + today.strftime("%Y%m01")
    current_log = access_log + "." + today.strftime("%Y_%b")
    return previous_log, current_log


def cat(*filenames):
    for fn in filenames:
        with open(fn) as f:
            for line in f:
                yield line


def pat(name, pattern):
    return "(?P<" + name + ">" + pattern + ")"


def pat_escaped_string(name):
    return '"' + pat(name, r'(?:\\"|[^"])*') + '"'


def pat_timestamp(name):
    return r"\[" + pat(name, r"../.../....:..:..:.. .....") + r"\]"


# from httpd.conf
# LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
COMBINED_LOG_PATTERN = (
    "^"
    + " ".join(
        [
            pat("h", r"\S+"),
            "-",
            pat("u", r".*?"),
            pat_timestamp("t"),
            pat_escaped_string("r"),
            pat("s", r"\d+"),
            pat("b", r"-|\d+"),
            pat_escaped_string("referer"),
            pat_escaped_string("user_agent"),
        ]
    )
    + "$"
)
COMBINED_LOG_RE = re.compile(COMBINED_LOG_PATTERN)


def parse(line):
    d = {}
    m = COMBINED_LOG_RE.match(line)
    if m:
        d = m.groupdict()
    return d


LOOKS_LIKE_A_NUMBER_RE = re.compile(r"^[-+]?[,.0-9]+$")


def apostrophize_number_as_text(n):
    s = str(n).strip()
    if LOOKS_LIKE_A_NUMBER_RE.match(s):
        return "'" + s
    else:
        return n


if __name__ == "__main__":
    sys.exit(main())
