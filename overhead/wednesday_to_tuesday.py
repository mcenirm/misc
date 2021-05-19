from __future__ import print_function
from datetime import date, timedelta

ISOWEDNESDAY = 3
ONEDAY = timedelta(days=1)
WEEKDAYFMT = "%a %b %d -"
WEEKENDFMT = "%a"

d = date.today()
for i in range(7 * 3):
    iwd = d.isoweekday()
    if d.isoweekday() == ISOWEDNESDAY:
        print()
    fmt = WEEKENDFMT if iwd > 5 else WEEKDAYFMT
    print(d.strftime(fmt))
    d += ONEDAY
