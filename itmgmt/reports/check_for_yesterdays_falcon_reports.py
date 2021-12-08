#!/usr/bin/env python
from __future__ import print_function

import collections
import csv
import datetime
import re
import subprocess
import sys
import urlparse


FIELD_LABELS = collections.OrderedDict(
    [
        ("result", "Result"),
        ("computer", "Computer"),
        ("ip", "IP"),
        ("user", "User"),
        ("date", "Date"),
        ("time", "Time"),
        ("zone", "Zone"),
        ("psbuild", "PSBuild"),
        ("tagged", "Tagged?"),
        ("tag", "Tag"),
        ("model", "Model"),
        ("osversion", "OS"),
        ("serial", "Serial"),
    ]
)


def main():
    date_expression = "yesterday"
    if len(sys.argv) > 1:
        date_expression = sys.argv[1]
    date_filter = (
        subprocess.Popen(
            [
                "date",
                "-d",
                date_expression,
                "+%d/%b/%Y",
            ],
            stdout=subprocess.PIPE,
        )
        .communicate()[0]
        .strip()
    )

    today = datetime.date.today()
    access_log = "{{ path to access log }}"
    previous_log = access_log + "-" + today.strftime("%Y%m01")
    current_log = access_log + "." + today.strftime("%Y_%b")

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
                    if not lead.lower().endswith("powershell"):
                        psbuild = "n/a"

                    record = dict(
                        ip=d["h"],
                        user=d["u"],
                        date=t_date,
                        time=t_time,
                        zone=t_zone,
                        psbuild=psbuild,
                        tagged="untagged",
                    )

                    method, path = d["r"].split(None, 1)
                    path, protocol = path.rsplit(None, 1)
                    d["method"] = method
                    d["path"] = path
                    d["query"] = urlparse.urlparse(path, "http").query
                    d["data"] = urlparse.parse_qs(d["query"])
                    if "tag" in d["data"]:
                        record["tagged"] = "tagged"
                    for k in [
                        "result",
                        "computer",
                        "tag",
                        "model",
                        "osversion",
                        "serial",
                    ]:
                        if k in d["data"]:
                            record[k] = d["data"][k][0]
                            del d["data"][k]
                        else:
                            record[k] = "n/a"
                    record["computer"] = record["computer"].split(".")[0]
                    record["serial"] = apostrophize_number_as_text(record["serial"])

                    for k in d["data"].keys():
                        record[k] = d["data"][k][0]
                        if not k in FIELD_LABELS:
                            print("** unexpected parameter:", k, file=sys.stderr)
                            FIELD_LABELS[k] = k

                    records.append(record)
        else:
            unparsed_lines.append(line)
    if unparsed_lines:
        print(unparsed_lines[0], file=sys.stderr)
        return 1
    if matched_lines:
        writer = csv.DictWriter(sys.stdout, FIELD_LABELS.keys())
        writer.writerow(FIELD_LABELS)
        writer.writerows(records)
    return 0


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


def apostrophize_number_as_text(n):
    s = str(n).strip()
    if len(s) > 0 and s[0] in "0123456789-+":
        return "'" + s
    else:
        return n


if __name__ == "__main__":
    sys.exit(main())
