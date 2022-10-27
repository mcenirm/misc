import csv
import pathlib

DATA = pathlib.Path("data")
PASSWD = "passwd"
GROUP = "group"


def load(path):
    d = {}
    with open(path) as f:
        for row in csv.reader(f, delimiter=":"):
            d[row[0]] = row
    return d


for dbname in [PASSWD, GROUP]:
    combined = load(DATA / dbname)
    by_host = {}
    for to_be_migrated in DATA.glob("*." + dbname):
        hostname = to_be_migrated.stem
        by_host[hostname] = load(to_be_migrated)
        migrate = DATA / ".".join([hostname, dbname, "migrate"])
        out = open(migrate, "w")
        count = 0
        for name in combined:
            if name not in by_host[hostname]:
                continue
            old_xid = by_host[hostname][name][2]
            new_xid = combined[name][2]
            if old_xid != new_xid:
                print(":".join([name, old_xid, new_xid]), file=out)
                count += 1
        if count > 0:
            print(count, migrate)
