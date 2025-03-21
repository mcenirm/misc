from __future__ import annotations

import codecs
import csv
import dataclasses
import encodings
import encodings.utf_7
import encodings.utf_8
import encodings.utf_8_sig
import encodings.utf_16_be
import encodings.utf_16_le
import encodings.utf_32_be
import encodings.utf_32_le
import io
import pathlib
import sys

import _csv


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
    encoding = guess_encoding_of_existing_file(csvname)
    return open(csvname, "r", encoding=encoding, newline="")


def open_file_for_csv_writer(csvname: str | pathlib.Path) -> io.TextIOBase:
    return open(csvname, "w", encoding="utf-8", newline="")


def guess_encoding_of_existing_file(filename: str | pathlib.Path) -> str | None:
    filename = pathlib.Path(filename)
    tests = [
        (codecs.BOM_UTF8, encodings.utf_8_sig),
        (codecs.BOM_UTF32_LE, encodings.utf_32_le),
        (codecs.BOM_UTF16_LE, encodings.utf_16_le),
        (codecs.BOM_UTF32_BE, encodings.utf_32_be),
        (codecs.BOM_UTF16_BE, encodings.utf_16_be),
    ]
    bom = filename.read_bytes()[: max([len(p) for p, em in tests])]
    for prefix, enc_mod in tests:
        if bom.startswith(prefix):
            break
    else:
        enc_mod = None
    if enc_mod is None:
        if bom.startswith(b"\x2b\x2f\x76"):
            if len(bom) > 3:
                follower = int.from_bytes(bom[3], "big")
                if 0x38 <= follower <= 0x3F:
                    enc_mod = encodings.utf_7
        elif b"\x00" not in bom:
            enc_mod = encodings.utf_8
    if enc_mod is None:
        return None
    return enc_mod.getregentry().name


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
