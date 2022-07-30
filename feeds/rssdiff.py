from __future__ import annotations

import pathlib
import xml.etree.ElementTree

from icecream import ic
from rich import inspect as ri


class ElementParentMap(dict):
    def __init__(self, root: xml.etree.ElementTree.Element):
        super().__init__(build_parent_map(root))

    def ancestors(
        self,
        e: xml.etree.ElementTree.Element,
    ) -> list[xml.etree.ElementTree.Element]:
        a = []
        while e in self and (p := self[e]) is not None:
            a.append(p)
            e = p
        return a


def main():
    from sys import argv

    rssdiff(pathlib.Path(argv[1]), pathlib.Path(argv[2]))


def rssdiff(left_path: pathlib.Path, right_path: pathlib.Path):
    from itertools import zip_longest

    lt = xml.etree.ElementTree.parse(left_path)
    rt = xml.etree.ElementTree.parse(right_path)
    lr = lt.getroot()
    rr = rt.getroot()
    lpm = ElementParentMap(lr)
    rpm = ElementParentMap(rr)

    left_iter, right_iter = list(lr.iter()), list(rr.iter())
    for i, leftright in enumerate(zip_longest(left_iter, right_iter)):
        left, right = leftright
        if left.tag != right.tag:
            ic(i, left, right, left.tag == right.tag)
            break
        if left.tag not in {"pubDate", "lastBuildDate"}:
            if left.text != right.text:
                ic(i, left, right, left.text, right.text)
                la = lpm.ancestors(left)
                ra = rpm.ancestors(right)
                lp = [_.tag for _ in reversed(la)]
                rp = [_.tag for _ in reversed(ra)]
                ic(lp, rp)
                break


def build_parent_map(
    root: xml.etree.ElementTree.Element,
) -> dict[xml.etree.ElementTree.Element, xml.etree.ElementTree.Element]:
    return {c: p for p in root.iter() for c in p}


if __name__ == "__main__":
    main()
