import time
from ast import literal_eval
from csv import DictReader
from pathlib import Path
from sys import argv
from types import SimpleNamespace

REPORT_TEST_FILENAME = Path(__file__).parent / "data/weird_report_test.csv"


def open_report_csv(fname):
    """open the report csv file and return a csv.DictReader"""
    f = open(fname, encoding="utf-8-sig")
    r = DictReader(f)
    return r


def convert_report_dict_to_object(report_dict):
    """convert each report dict to an object"""
    o = SimpleNamespace()
    setattr(o, "unhandled", {})
    for k, v in report_dict.items():
        if k in {"VULN_ID", "NAME", "QID", "PAYLOAD REQUEST", "status"}:
            attr_name = k.lower().replace(" ", "_")
            setattr(o, attr_name, v)
        elif k == "50":
            o.request_url = v
        elif k == "PAYLOAD RESPONSE":
            report_bytes = literal_eval(v)
            o.report = report_bytes.decode()
        else:
            o.unhandled[k] = v
    return o


def print_section(file=None):
    print(file=file)
    print("=" * 60, file=file)
    print(file=file)


def clean_status(status):
    status = status.lower()
    status = status.replace(" ", "_")
    status = status.replace("?", "")
    return status


if __name__ == "__main__":
    fname = argv[1] if len(argv) > 1 else REPORT_TEST_FILENAME
    r = open_report_csv(fname)
    now = str(int(time.time()))
    outs = {}
    for row in r:
        o = convert_report_dict_to_object(row)
        out = outs.get(o.status)
        if out is None:
            out = open(f"results.{now}.{clean_status(o.status)}.txt", "w")
            outs[o.status] = out
        print_section(file=out)
        print("Vuln ID:", o.vuln_id, file=out)
        print("QID:    ", o.qid, file=out)
        print("Name:   ", o.name, file=out)
        print("URL:    ", o.request_url, file=out)
        print("Request:", o.payload_request, file=out)
        print("Report:", file=out)
        print(o.report, file=out)
        # print("Unhandled fields:", o.unhandled, file=out)
    for out in outs.values():
        print_section(file=out)
        out.close()
