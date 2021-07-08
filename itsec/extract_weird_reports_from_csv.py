from ast import literal_eval
from csv import DictReader
from pathlib import Path
from sys import argv

REPORT_KEY = "TODO report key"
REPORT_TEST_FILENAME = Path(__file__).parent / "data/weird_report_test.csv"

fname = argv[1] if len(argv) > 1 else REPORT_TEST_FILENAME
f = open(fname)
with f:
    r = DictReader(f)
    for row in r:
        report_bytes_literal = row[REPORT_KEY]
        print(type(report_bytes_literal), report_bytes_literal)
        report_bytes = literal_eval(report_bytes_literal)
        print(type(report_bytes), report_bytes)
        report = report_bytes.decode()
        print(type(report), report)
