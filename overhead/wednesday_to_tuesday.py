from __future__ import annotations

from datetime import date, datetime, timedelta
from sys import argv, exit, stderr
from typing import Iterable

ISOWEDNESDAY = 3
ONEDAY = timedelta(days=1)
WEEKDAYFMT = "%a %b %d -"
WEEKENDFMT = "%a"
STARTDATESTRPTIMEFORMATS = [
    "%Y-%m-%d",
]


def attempt_strptime_using_several_formats(
    datetime_string: str,
    formats: Iterable[str],
) -> datetime:
    for fmt in formats:
        try:
            return datetime.strptime(datetime_string, fmt)
        except ValueError:
            pass
    raise ValueError(f"unable to strptime: {datetime_string!r}")


if argv[1:]:
    try:
        d = attempt_strptime_using_several_formats(
            argv[1],
            STARTDATESTRPTIMEFORMATS,
        ).date()
    except ValueError as ve:
        print("Error:", *ve.args, file=stderr)
        exit(1)
else:
    d = date.today()

for i in range(7 * 3):
    iwd = d.isoweekday()
    if d.isoweekday() == ISOWEDNESDAY:
        print()
    fmt = WEEKENDFMT if iwd > 5 else WEEKDAYFMT
    print(d.strftime(fmt))
    d += ONEDAY
