from __future__ import annotations

import csv
import dataclasses
import io
import pathlib
import sys

import _csv

import frustra.guess_encoding_of_existing_file

# TODO Fix bad quoting, such as: ... 2.5" Chassis ...

# TODO Fix spurious space at 42, 73 (30 char runs?)
# -----------------------------------------v------------------------------v---
# 340-CWUJ : PowerEdge R350/R360 Shipping M aterial ...
# 329-BJTG : PowerEdge R360 Motherboard wit h LOM ...
# 338-CMQL : Intel Xeon E-2488 3.2G, 8C/16T , 24M Cache, Turbo, HT (95W) D DR5
# 540-BCRQ : Intel X710-T2L Dual Port 10GbE  BASE-T Adapter, PCIe Low Prof ile
# -----------------------------------------^------------------------------^---


@dataclasses.dataclass
class FixStats:
    total_rows: int = 0
    total_components: int = 0
    total_rows_fixed: int = 0


def fix_dell_system_configuration_export_csv(
    readfrom: _csv.Reader, writeto: _csv.Writer
) -> FixStats:
    stats = FixStats()
    component = None
    for rownum, row in enumerate(readfrom, 1):
        if not (rownum == 1 and row[0] == "Component"):
            stats.total_rows += 1
            if row[0] and row[0] != " : ":
                component = row[0]
                stats.total_components += 1
            elif component is not None:
                row[0] = component
                stats.total_rows_fixed += 1
        writeto.writerow(row)
    return stats


def open_file_for_csv_reader(csvname: str | pathlib.Path) -> io.TextIOBase:
    encoding = frustra.guess_encoding_of_existing_file.guess_encoding_of_existing_file(
        csvname
    )
    return open(csvname, "r", encoding=encoding, newline="")


def open_file_for_csv_writer(csvname: str | pathlib.Path) -> io.TextIOBase:
    return open(csvname, "w", encoding="utf-8", newline="")


def main():
    if len(sys.argv) < 2:
        print(
            "Usage:",
            "python",
            pathlib.Path(__file__).name,
            "X1Y2Z34.csv",
            "[...]",
            file=sys.stderr,
        )
        sys.exit(1)
    for arg in sys.argv[1:]:
        orig = pathlib.Path(arg)
        fixed = orig.with_name("fixed-" + orig.name)
        origfile = open_file_for_csv_reader(orig)
        fixedfile = open_file_for_csv_writer(fixed)
        with origfile, fixedfile:
            origreader = csv.reader(origfile, dialect=csv.excel)
            fixedwriter = csv.writer(fixedfile, dialect=csv.excel)
            stats = fix_dell_system_configuration_export_csv(origreader, fixedwriter)
            print(
                fixed,
                f"(rows: {stats.total_rows}, components: {stats.total_components}, fixed rows: {stats.total_rows_fixed})",
            )


if __name__ == "__main__":
    main()
