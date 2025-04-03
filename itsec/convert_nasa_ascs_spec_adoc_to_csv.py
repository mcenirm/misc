from __future__ import annotations

import csv
import dataclasses
import pathlib
import re
import sys
import typing


if typing.TYPE_CHECKING:
    from _typeshed import SupportsWrite

from frustra.csvs import open_file_for_csv_writer
from frustra.strings import str_to_identifier


@dataclasses.dataclass
class Setting:
    nasa_ascs_id: str = None
    severity: str = None
    path: str = None
    nasa_control: str = None
    control_setting: str = None
    type_: str = None
    title: str = None
    nist_sp_800_53r5_reference: str = None
    stig_reference: str = None
    linenum: int = None


def guess_setting_from_dict(d: dict[str, str]) -> Setting:
    return Setting(**d)


class Specification:
    def __init__(self, lines: list[str]):
        self.lines = [str(s) for s in lines]
        self.settings: list[Setting] = []
        self.document_identifier: str = None
        self.document_version: str = None

        md = None
        s = None
        t = None
        for linenum, line in enumerate(self.lines, 1):
            m_heading = re.compile(r"=+\s+(?P<title>NASA-ASCS-\d+:\s+.*\S)\s*").match(
                line
            )
            if m_heading:
                if s is None:
                    s = dict(m_heading.groupdict())
                    s["linenum"] = linenum
                else:
                    self.settings.append(guess_setting_from_dict(s))
                    s = None
                    t = None
                continue

            if s is None:
                m_doc = re.compile(
                    r":(?P<n>document-identifier|document-version):\s+(?P<v>.*\S)\s*$"
                ).match(line)
                if m_doc:
                    n = m_doc.group("n")
                    v = m_doc.group("v")
                    n = str_to_identifier(n)
                    if md is None:
                        md = {}
                    md[n] = v
                    continue
                else:
                    # Skip everything before first setting block
                    continue

            if line.startswith("[cols="):
                # Skip table attribute inside setting block
                continue

            if line == "|===":
                # Table begin vs end
                if t is None:
                    t = True
                else:
                    t = None
                continue

            if t is None:
                # Skip everything else that is not inside the table
                continue

            m_nv = re.compile(r"\|(?P<n>[^|]+)\|(?P<v>.*)$").match(line)
            if m_nv:
                # Get name and value from table row
                n = m_nv.group("n")
                v = m_nv.group("v")
                n = str_to_identifier(n)
                s[n] = v
                continue

            raise ValueError(
                "Unexpected line in setting table",
                dict(linenum=linenum, line=line, setting=s),
            )

        if s is not None:
            self.settings.append(guess_setting_from_dict(s))

        if md is not None:
            self.document_identifier = md.get("document_identifier")
            self.document_version = md.get("document_version")


def spec_to_csv(spec: Specification, csvout: SupportsWrite[str]) -> None:
    w = csv.DictWriter(csvout, [f.name for f in dataclasses.fields(Setting)])
    w.writeheader()
    for setting in spec.settings:
        w.writerow(dataclasses.asdict(setting))


def main():
    spec_filename = sys.argv[1]
    spec_path = pathlib.Path(spec_filename)
    spec_text = spec_path.read_text()
    spec_lines = spec_text.splitlines()
    spec = Specification(spec_lines)

    outstem = spec_path.stem
    if spec.document_identifier:
        outstem = spec.document_identifier
        if spec.document_version:
            outstem += " " + spec.document_version
    out_path = pathlib.Path(outstem + ".csv")

    print("Writing:", out_path)
    with open_file_for_csv_writer(out_path) as out:
        spec_to_csv(spec, out)


if __name__ == "__main__":
    main()
