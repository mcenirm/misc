from __future__ import annotations

import dataclasses
import pathlib
import typing
import xml.etree.ElementTree

from icecream import ic
from rich import inspect as ri

CANDIDATE_ITEM_IDS = {"guid", "link", "title"}
RDF_CONTENT_ENCODED_QNAME = r"{http://purl.org/rss/1.0/modules/content/}encoded"
MRSS_THUMBNAIL_QNAME = r"{http://search.yahoo.com/mrss/}thumbnail"
SNF_ADVERTISEMENT_QNAME = r"{http://www.smartnews.be/snf}advertisement"
SNF_ANALYTICS_QNAME = r"{http://www.smartnews.be/snf}analytics"
FIELD_QNAME_MAP = {
    "rdf_content_encoded": RDF_CONTENT_ENCODED_QNAME,
    "mrss_thumbnail": MRSS_THUMBNAIL_QNAME,
    "snf_advertisement": SNF_ADVERTISEMENT_QNAME,
    "snf_analytics": SNF_ANALYTICS_QNAME,
}
QNAME_FIELD_MAP = {v: k for k, v in FIELD_QNAME_MAP.items()}


RssElementType = typing.TypeVar("RssElementType", bound="RssElement")


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


@dataclasses.dataclass(kw_only=True, frozen=True)
class RssElement:
    _elem: xml.etree.ElementTree.Element
    _extras: list[xml.etree.ElementTree.Element]

    @classmethod
    def from_(
        cls: typing.Type[RssElementType], elem: xml.etree.ElementTree.Element
    ) -> RssElementType:
        from inspect import get_annotations
        from types import UnionType

        class_annotations = get_annotations(cls, eval_str=True)
        extras = []
        kwargs = {"_elem": elem, "_extras": extras}
        for child in elem:
            field_name = QNAME_FIELD_MAP.get(child.tag, child.tag)
            annotation = class_annotations.get(field_name)
            annotation_args = typing.get_args(annotation)
            match annotation:
                case UnionType():
                    if str in annotation_args:
                        kwargs[field_name] = innertext(child)
                case None:
                    extras.append(child)
                case _:
                    ic(annotation, type(annotation))
                    raise NotImplementedError(
                        "TODO don't know how to handle annotation"
                    )
        return cls(**kwargs)


@dataclasses.dataclass(kw_only=True, frozen=True)
class RssItem(RssElement):
    author: str | None
    description: str | None
    guid: str | None
    link: str | None
    pubDate: str | None
    title: str | None
    rdf_content_encoded: str | None
    mrss_thumbnail: str | None
    snf_advertisement: str | None
    snf_analytics: str | None


@dataclasses.dataclass(kw_only=True, frozen=True)
class RssChannel(RssElement):
    copyright: str | None
    description: str | None
    language: str | None
    lastBuildDate: str | None
    link: str | None
    pubDate: str | None
    snf_logo: str | None

    item: list[RssItem] = dataclasses.field(default_factory=list)


def main():
    from sys import argv

    rssdiff(pathlib.Path(argv[1]), pathlib.Path(argv[2]))


def rssdiff(left_path: pathlib.Path, right_path: pathlib.Path):
    from collections import defaultdict
    from itertools import zip_longest

    ET = xml.etree.ElementTree

    paths = [left_path, right_path]
    labels = ["left", "right"]
    index_by_label = {label: i for i, label in enumerate(labels)}
    trees = [ET.parse(path) for path in paths]
    rsses = [tree.getroot() for tree in trees]
    parent_maps = [ElementParentMap(rss) for rss in rsses]
    for label, root in zip(labels, rsses):
        expected = "rss"
        actual = root.tag
        assert root.tag == expected, "".join(
            [
                "unexpected root for ",
                str(label),
                ": expected ",
                repr(expected),
                ", got ",
                repr(actual),
            ]
        )
    chans = [rss.find("channel") for rss in rsses]
    for label, chan in zip(labels, chans):
        tag = "channel"
        assert chan is not None, f"missing {tag} for {label}"

    for label, chan_el in zip(labels, chans):
        chan = RssChannel.from_(chan_el)
        ic(chan.title)
        ic({_.tag for _ in chan._extras})

    chan_child_tags = [build_child_tag_set(chan) for chan in chans]
    all_chan_child_tags = set.union(*chan_child_tags)
    for tag in sorted(all_chan_child_tags):
        for i, (label, chan) in enumerate(zip(labels, chans)):
            assert tag in chan_child_tags[i], "".join(
                ["missing child ", repr(tag), " for ", str(label)]
            )
    chan_prop_maps = [{} for _ in chans]
    chan_item_lists: list[list[ET.Element]] = [[] for _ in chans]
    for i, (label, chan) in enumerate(zip(labels, chans)):
        for child in chan:
            tag = child.tag
            if tag != "item":
                assert tag not in chan_prop_maps[i], "".join(
                    [
                        "unexpected duplicate of property ",
                        repr(tag),
                        " for ",
                        str(label),
                    ]
                )
                chan_prop_maps[i][tag] = "".join(map(str.strip, child.itertext()))
            else:
                chan_item_lists[i].append(child)

    items_by_label_and_id: dict[tuple[str, str], RssItem] = {}
    expected_child_tags: set | None = None
    for label, chan_item_list in zip(labels, chan_item_lists):
        for item_el in chan_item_list:
            child_tags = build_child_tag_set(item_el)
            if expected_child_tags is None:
                expected_child_tags = set(child_tags)
            assert child_tags == expected_child_tags, "".join(
                [
                    "item child tag mismatch for ",
                    str(label),
                    ": ",
                    ("".join(map(str.strip, item_el.itertext())))[:30],
                ]
            )
            item = RssItem.from_(item_el)
            raise NotImplementedError("TODO")
        ic(label, len(chan_item_list))
    ic(sorted(expected_child_tags))


def build_parent_map(
    root: xml.etree.ElementTree.Element,
) -> dict[xml.etree.ElementTree.Element, xml.etree.ElementTree.Element]:
    return {c: p for p in root.iter() for c in p}


def build_child_tag_set(elem: xml.etree.ElementTree.Element | None) -> set[str] | None:
    if elem is None:
        return None
    return {child.tag for child in elem}


def innertext(elem: xml.etree.ElementTree.Element | None, sep: str = "") -> str | None:
    """

    >>> innertext(_pxs("<simple>something simple</simple>"))
    'something simple'
    >>> innertext(_pxs("<a><b>1<c>2<d/>3</c></b>4</a>"))
    '1234'

    """

    if elem is None:
        return None
    return sep.join(elem.itertext())


def _pxs(data: str) -> xml.etree.ElementTree.Element:
    import xml.etree.ElementTree as ET
    from io import StringIO

    return ET.parse(StringIO(data)).getroot()


if __name__ == "__main__":
    from doctest import FAIL_FAST as _FF
    from doctest import testmod as _tm

    _tm(optionflags=_FF, raise_on_error=True)

    main()
