import io
import pathlib

from .guess_encoding_of_existing_file import guess_encoding_of_existing_file


def open_file_for_csv_reader(csvname: str | pathlib.Path) -> io.TextIOBase:
    encoding = guess_encoding_of_existing_file(csvname)
    return open(csvname, "r", encoding=encoding, newline="")


def open_file_for_csv_writer(csvname: str | pathlib.Path) -> io.TextIOBase:
    return open(csvname, "w", encoding="utf-8", newline="")
