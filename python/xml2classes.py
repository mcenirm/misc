from __future__ import annotations

import sys
import xml.etree.ElementTree as _ET

from icecream import ic
from rich import inspect as ri


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


def main():
    nsmap = build_nsmap(sys.argv[1:])
    tree = _ET.parse(sys.stdin)
    for e in tree.iter():
        uri = get_xmlns_uri_from_qualified_tag(e.tag)
        if uri not in nsmap:
            ic("unrecognized xmlns", uri)
            ri(e)
            break
    parent_map = {c: p for p in tree.iter() for c in p}
    root = tree.getroot()
    ri(root)


if __name__ == "__main__":
    if sys.argv[1:] == ["--doctest"]:
        import doctest

        doctest.testmod(optionflags=doctest.FAIL_FAST)
    else:
        main()
