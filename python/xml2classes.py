from __future__ import annotations

import collections
import dataclasses
import sys
import typing
import xml.etree.ElementTree as _ET

from icecream import ic
from rich import inspect as ri


@dataclasses.dataclass(kw_only=True, frozen=True)
class ConnectionCounter:
    tag: str
    parents: dict = dataclasses.field(
        default_factory=lambda: collections.defaultdict(int)
    )


@dataclasses.dataclass(kw_only=True, frozen=True)
class TagNameAndUri:
    tag: str
    uri: str | None = dataclasses.field(init=False)
    name: str = dataclasses.field(init=False)

    def __post_init__(self) -> None:
        uri, name = split_tag(self.tag)
        object.__setattr__(self, "uri", uri)
        object.__setattr__(self, "name", name)


@dataclasses.dataclass(kw_only=True, frozen=True)
class XmlnsPrefixMarker:
    uri: str | None
    prefix: str | None
    elem: _ET.Element | None


def build_nsmap(args: list[str]) -> dict[str, str]:
    """

    # no namespaces, but pretend default namespace exists
    >>> build_nsmap([])
    {None: None}
    >>> build_nsmap(["foo=urn:foo", "bar=urn:bar"])
    {'foo': 'urn:foo', 'bar': 'urn:bar'}
    >>> build_nsmap(["urn:foo", "bar=urn:bar"])
    {None: 'urn:foo', 'bar': 'urn:bar'}
    >>> build_nsmap(["foo=urn:foo", "foo=urn:bar"])
    {'foo': 'urn:bar'}

    # TODO strip "xmlns:"?
    # >>> build_nsmap(["xmlns:foo=urn:foo"])
    # {'foo': 'urn:foo'}
    """

    nsmap = {}
    for arg in args:
        if "=" in arg:
            prefix, uri = arg.split("=", maxsplit=1)
        else:
            prefix, uri = None, arg
        # TODO decide about duplicated prefixes (probably ignore, but maybe error?)
        nsmap[prefix] = uri
    if not nsmap:
        nsmap = {None: None}
    return nsmap


def split_tag(tag: str) -> tuple[str | None, str]:
    """

    >>> split_tag("foo")
    (None, 'foo')
    >>> split_tag("{urn:foo}bar")
    ('urn:foo', 'bar')

    """

    if tag[0] == "{":
        uri, name = tag[1:].split("}", maxsplit=1)
        return uri, name
    return None, tag


def get_xmlns_uri_from_qualified_tag(tag: str) -> str | None:
    """

    >>> get_xmlns_uri_from_qualified_tag("foo")
    >>> get_xmlns_uri_from_qualified_tag("{urn:foo}bar")
    'urn:foo'

    """

    if tag[0] == "{":
        uri, _ = tag[1:].split("}", maxsplit=1)
        return uri
    return None


@dataclasses.dataclass(kw_only=True, frozen=True)
class ClassFromElement:
    tag: TagNameAndUri

    @classmethod
    def from_(cls, el: _ET.Element) -> ClassFromElement:
        tag = TagNameAndUri(tag=el.tag)
        cfe = cls(tag=tag)
        return cfe

    def update(self, data):
        ...


class Builder:
    def __init__(self) -> None:
        self.root: _ET.Element | None = None
        self.nsmap = collections.defaultdict(lambda: collections.defaultdict(list))
        self.classmap: dict[str, ClassFromElement] = {}
        self.parentmap: dict[_ET.Element, _ET.Element] = {}

    def load(self, f: typing.TextIO):
        ns_queue = []
        for event, data in _ET.iterparse(
            f, events=["start", "end", "comment", "pi", "start-ns", "end-ns"]
        ):
            match event:
                case "start-ns":
                    ns_queue.append(data)
                case "start":
                    if self.root is None:
                        self.root = data
                    while ns_queue:
                        prefix, uri = ns_queue.pop()
                        self.nsmap[uri][prefix].append(data)
                case "end":
                    cfe = self.classmap.get(data.tag)
                    if cfe is None:
                        cfe = ClassFromElement.from_(data)
                        self.classmap[data.tag] = cfe
                    cfe.update(data)
        self.parentmap.update(build_parent_map(self.root))


class keydefaultdict(collections.defaultdict):
    "https://stackoverflow.com/a/2912455"

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        else:
            ret = self[key] = self.default_factory(key)
            return ret


def build_parent_map(root: _ET.Element) -> dict[_ET.Element, _ET.Element]:
    return {c: p for p in root.iter() for c in p}


CLASS_TEMPLATE_1 = """
@dataclasses.dataclass(kw_only=True, frozen=True)
class {}
"""


def count_connections(tree: _ET.Element) -> dict[str, ConnectionCounter]:
    counts = keydefaultdict(lambda k: ConnectionCounter(tag=k))
    parentmap = build_parent_map(tree)
    for el in tree.iter():
        match el:
            case _ET.Element():
                p = parentmap.get(el)
                if p:
                    cc: ConnectionCounter = counts[el.tag]
                    cc.parents[p.tag] += 1
            case _:
                raise NotImplementedError("unhandled", el)
    return counts


def longest_common_prefix(strs: list[str]) -> str | None:
    """

    >>> longest_common_prefix([])
    >>> longest_common_prefix(["a",None,"b"])
    >>> longest_common_prefix(["a","","b"])
    ''
    >>> longest_common_prefix(["a","b"])
    ''
    >>> longest_common_prefix(["aa","ab","ac"])
    'a'
    >>> longest_common_prefix(["abc","ab","a"])
    'a'
    >>> longest_common_prefix(["aaaaa","aaaa","aaaaaa"])
    'aaaa'

    """

    for s in strs or [None]:
        if s is None:
            return None
        if s == "":
            return ""
    i = 0
    s0 = strs[0]
    ss = strs[1:]
    try:
        while True:
            ch = s0[i]
            for s in ss:
                if s[i] != ch:
                    return s0[:i]
            i += 1
    except IndexError:
        return s0[:i]


def print_clunky_parent_child_table(counts: dict[str, ConnectionCounter]) -> None:
    sorted_ctags = sorted(counts.keys())
    sorted_ptags = sorted({pt for cc in counts.values() for pt in cc.parents.keys()})
    prefix = longest_common_prefix(list(set(sorted_ctags + sorted_ptags)))
    prefix_len = len(prefix)
    ctag_width = max(len(ct) for ct in sorted_ctags) - prefix_len
    col_widths = [ctag_width] + [len(pt) - prefix_len for pt in sorted_ptags]
    col_fmts = ["{:^" + str(w) + "}" for w in col_widths]
    col_fmts[0] = col_fmts[0][:2] + ">" + col_fmts[0][3:]
    print(*([" " * ctag_width] + [pt[prefix_len:] for pt in sorted_ptags]))
    print(*["-" * w for w in col_widths])
    for ct in sorted_ctags:
        print(
            *[
                fmt.format(s)
                for fmt, s in zip(
                    col_fmts,
                    [ct[prefix_len:]]
                    + [counts[ct].parents[pt] or "" for pt in sorted_ptags],
                )
            ]
        )


def main():
    bldr = Builder()
    bldr.load(sys.stdin)
    ic(bldr.root.tag, bldr.root.attrib, len(bldr.root))
    counts = count_connections(bldr.root)
    print_clunky_parent_child_table(counts=counts)
    # root_class = ClassFromElement.from_(bldr.root)
    # ic(root_class)


if __name__ == "__main__":
    if sys.argv[1:] == ["--doctest"]:
        import doctest

        doctest.testmod(optionflags=doctest.FAIL_FAST)
    else:
        main()
