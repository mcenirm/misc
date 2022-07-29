from __future__ import annotations
import pathlib

from icecream import ic
from rich import inspect as ri


def main():
    from sys import argv

    rssdiff(pathlib.Path(argv[1]), pathlib.Path(argv[2]))


def rssdiff(left_path: pathlib.Path, right_path: pathlib.Path):
    import xml.etree.ElementTree as ET
    from itertools import zip_longest

    lt, rt = ET.parse(left_path), ET.parse(right_path)
    lr, rr = lt.getroot(), rt.getroot()

    left_iter, right_iter = list(lr.iter()), list(rr.iter())
    for i, leftright in enumerate(zip_longest(left_iter, right_iter)):
        left, right = leftright
        if left.tag != right.tag:
            ic(i, left, right, left.tag == right.tag)
            break
        if left.tag not in {"pubDate", "lastBuildDate"}:
            if left.text != right.text:
                ic(i, left, right, left.text, right.text)
                break


if __name__ == "__main__":
    main()
