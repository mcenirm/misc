from __future__ import annotations

import csv
import dataclasses
import io
import pathlib
import typing

from .guess_encoding_of_existing_file import guess_encoding_of_existing_file

if typing.TYPE_CHECKING:
    from _typeshed import DataclassInstance, SupportsWrite


def open_file_for_csv_reader(csvname: str | pathlib.Path) -> io.TextIOBase:
    encoding = guess_encoding_of_existing_file(csvname)
    return open(csvname, "r", encoding=encoding, newline="")


def open_file_for_csv_writer(csvname: str | pathlib.Path) -> io.TextIOBase:
    return open(csvname, "w", encoding="utf-8", newline="")


def save_dataclass_list_as_csv(
    csvout: SupportsWrite,
    items: list[DataclassInstance],
    prune_empty_columns=True,
) -> None:
    fieldnames = []
    fields_with_values = set()
    rows = []
    for item in items:
        fieldnames.extend(
            [f.name for f in dataclasses.fields(item) if f.name not in fieldnames]
        )
        d = {k: v for k, v in dataclasses.asdict(item).items() if v is not None}
        rows.append(d)
        fields_with_values.update(d.keys())
    if prune_empty_columns:
        fieldnames = [n for n in fieldnames if n in fields_with_values]
    w = csv.DictWriter(csvout, fieldnames)
    w.writeheader()
    w.writerows(rowdicts=rows)
