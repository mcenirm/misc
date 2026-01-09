from __future__ import annotations

import collections
import doctest
import enum
import pathlib
import sys
import xml.etree.ElementTree as ET


def _ns_tag(ns: str, tag: str) -> str:
    """
    >>> _ns_tag("uri", "tag")
    '{uri}tag'
    """

    return "{" + str(ns) + "}" + str(tag)


XCCDF_NS = "http://checklists.nist.gov/xccdf/1.2"
XCCDF_RULE_QNAME = _ns_tag(XCCDF_NS, "Rule")
XCCDF_CHECK_QNAME = _ns_tag(XCCDF_NS, "check")
XCCDF_VERSION_QNAME = _ns_tag(XCCDF_NS, "version")
XCCDF_TITLE_QNAME = _ns_tag(XCCDF_NS, "title")
XCCDF_SELECTOR = "selector"


class XccdfCheckSelector(enum.StrEnum):
    BLANK = ""
    AUTOMATED = "automated"
    MANUAL = "manual"


def main():
    enhanced_benchmark_file = pathlib.Path(sys.argv[1])

    tree = ET.parse(enhanced_benchmark_file)
    root = tree.getroot()
    for rule_number, rule in enumerate(root.findall(".//" + XCCDF_RULE_QNAME), 1):
        checks_by_selector: dict[str, list[ET.Element]] = collections.defaultdict(list)
        for check in rule.findall(XCCDF_CHECK_QNAME):
            selector = check.get(XCCDF_SELECTOR)
            if selector is None:
                raise NotImplementedError(
                    "expected " + repr(XCCDF_SELECTOR), check, check.attrib, rule
                )
            checks_by_selector[selector].append(check)
        selectors = set([XccdfCheckSelector(s) for s in checks_by_selector.keys()])
        if (
            XccdfCheckSelector.MANUAL in selectors
            and XccdfCheckSelector.AUTOMATED not in selectors
        ):
            version = _er(rule.find(XCCDF_VERSION_QNAME)) or "??"
            title = _er(rule.find(XCCDF_TITLE_QNAME)) or "??"
            print(
                rule_number,
                sorted([s.lower() for s in selectors]),
                version,
                title,
            )


def _print_xmlns_uris_and_prefixes(f: pathlib.Path) -> None:
    namespaces: dict[str, set[str]] = collections.defaultdict(set)
    for _, elem in ET.iterparse(f, events=["start-ns"]):
        prefix, uri = tuple(map(str, elem))
        namespaces[uri].add(prefix)
    for uri, prefixes in sorted(namespaces.items()):
        if len(prefixes) > 1:
            print("--", repr(uri), len(prefixes), prefixes)
        else:
            print("--", repr(uri), repr(next(iter(prefixes))))


def _er(elem: ET.Element | None) -> str | None:
    if elem is not None and elem.text is not None:
        return repr(elem.text)
    else:
        return None


if __name__ == "__main__":
    if "--doctest" in sys.argv[1:]:
        doctest.testmod(optionflags=doctest.FAIL_FAST | doctest.ELLIPSIS)
    else:
        main()
