from __future__ import annotations

import ast as _ast
import collections as _collections
import dataclasses as _dataclasses
import io as _io
import sys as _sys
import typing as _typing
import xml.etree.ElementTree as _ET

from icecream import ic
from rich import inspect as ri


@_dataclasses.dataclass(kw_only=True, frozen=True)
class ConnectionCounter:
    tag: str
    parents: dict = _dataclasses.field(
        default_factory=lambda: _collections.defaultdict(int)
    )


@_dataclasses.dataclass(kw_only=True, frozen=True)
class TagNameAndUri:
    """

    >>> t = TagNameAndUri(tag="a")
    >>> t.uri, t.name
    (None, 'a')
    >>> t = TagNameAndUri(tag="{urn:x}a")
    >>> t.uri, t.name
    ('urn:x', 'a')
    """

    tag: str
    uri: str | None = _dataclasses.field(init=False)
    name: str = _dataclasses.field(init=False)

    def __post_init__(self) -> None:
        uri, name = split_tag(self.tag)
        object.__setattr__(self, "uri", uri)
        object.__setattr__(self, "name", name)


@_dataclasses.dataclass(kw_only=True, frozen=True)
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


@_dataclasses.dataclass(kw_only=True, frozen=True)
class ClassFromElement:
    """

    >>> _ast.unparse(ClassFromElement.from_(_mxt("<a/>").getroot()).as_ast())
    'class a:\\n    ...'
    """

    tag: TagNameAndUri

    @classmethod
    def from_(cls, el: _ET.Element) -> ClassFromElement:
        tag = TagNameAndUri(tag=el.tag)
        cfe = cls(tag=tag)
        return cfe

    def update(self, data):
        ...

    def as_ast(self) -> _ast.ClassDef:
        return _ast.ClassDef(
            name=self.tag.name,
            bases=[],
            keywords=[],
            body=[
                _ast.Expr(value=_ast.Constant(value=Ellipsis)),
            ],
            decorator_list=[],
        )


class Builder:
    """

    >>> Builder().load(_mxf("<a/>")).build()[0].tag.uri is None
    True
    >>> Builder().load(_mxf("<a xmlns='urn:x'/>")).build()[0].tag.uri
    'urn:x'
    """

    def __init__(self) -> None:
        self.root: _ET.Element | None = None
        self.nsmap = _collections.defaultdict(lambda: _collections.defaultdict(list))
        self.classmap: dict[str, ClassFromElement] = {}
        self.parentmap: dict[_ET.Element, _ET.Element] = {}

    def load(self, f: _io.TextIO) -> Builder:
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
        return self

    def build(self) -> list[ClassFromElement]:
        return list(self.classmap.values())


class keydefaultdict(_collections.defaultdict):
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
@_dataclasses.dataclass(kw_only=True, frozen=True)
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


class ElementTreeParentMap(_typing.Mapping[_ET.Element, _ET.Element]):
    """

    >>> tree, pmap = _mtp("<a><b><c1/><c2/></b></a>")
    >>> root = tree.getroot()
    >>> b = root.find("b")
    >>> c1 = b.find("c1")
    >>> pmap[root] is None
    True
    >>> pmap[b] == root
    True
    >>> pmap[c1] == b
    True
    >>> tuple(map(len, map(set, (pmap, pmap.keys(), pmap.values()))))
    (4, 4, 3)
    """

    def __init__(self, tree: _ET.ElementTree) -> None:
        self._tree = tree
        self._map = dict()
        self._map[tree.getroot()] = None
        for p in tree.iter():
            for c in p:
                self._map[c] = p

    def __getitem__(self, key: _ET.Element) -> _ET.Element:
        return self._map[key]

    def __iter__(self) -> _typing.Iterator[_ET.Element]:
        return iter(self._map)

    def __len__(self) -> int:
        return len(self._map)

    def ancestors(self, e: _ET.Element) -> _typing.Generator[_ET.Element, None, None]:
        """

        >>> tree, pmap = _mtp("<a><b><c1/><c2/></b></a>")
        >>> c2 = tree.getroot()[0][1]
        >>> c2.tag
        'c2'
        >>> for p in pmap.ancestors(c2):
        ...     p.tag
        'b'
        'a'
        """
        p = e
        while (p := self[p]) is not None:
            yield p


def short_tag(tag: str) -> str:
    """

    >>> short_tag("foo")
    'foo'
    >>> short_tag("{foo}bar")
    'bar'
    """
    return tag.split("}")[-1]


def _mtp(x: str) -> tuple[_ET.ElementTree, ElementTreeParentMap]:
    tree = _mxt(x)
    pmap = ElementTreeParentMap(tree)
    return tree, pmap


def _mxt(x: str) -> _ET.ElementTree:
    from io import StringIO

    return _ET.parse(StringIO(x))


def _mxf(x: str) -> _io.TextIO:
    from io import StringIO

    f = StringIO(x)
    return f


def run(infile: _io.TextIO, outfile: _io.TextIO | None = None) -> None:
    """

    >>> run(_mxf("<a/>"))
    class a:
        ...
    """

    print_kwargs = dict()
    if outfile is not None:
        print_kwargs["file"] = outfile
    bldr = Builder()
    bldr.load(infile)
    for cfe in bldr.build():
        print(_ast.unparse(cfe.as_ast()), **print_kwargs)


def main():
    run(_sys.stdin, _sys.stdout)


if __name__ == "__main__":
    if _sys.argv[1:] == ["--doctest"]:
        import doctest

        doctest.testmod(optionflags=doctest.FAIL_FAST)
    else:
        main()
