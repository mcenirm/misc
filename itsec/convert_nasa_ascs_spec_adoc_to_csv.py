from __future__ import annotations

import pathlib
import sys
import typing

if typing.TYPE_CHECKING:
    from _typeshed import SupportsWrite

from nasa_ascs import Specification

from frustra.csvs import open_file_for_csv_writer, save_dataclass_list_as_csv


def spec_to_csv(spec: Specification, csvout: SupportsWrite[str]) -> None:
    save_dataclass_list_as_csv(csvout, spec.settings)


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
