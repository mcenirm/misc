from __future__ import annotations

import doctest
import pathlib
import sys
import typing
import xml.etree.ElementTree as ET

XSD_XMLNS = "http://www.w3.org/2001/XMLSchema"
XSD_SCHEMA_TAG = "{" + XSD_XMLNS + "}schema"
XSD_TARGET_NAMESPACE_ATTR = "targetNamespace"

XML_CATALOG_XMLNS = "urn:oasis:names:tc:entity:xmlns:xml:catalog"
XML_CATALOG_CATALOG_TAG = "{" + XML_CATALOG_XMLNS + "}catalog"
XML_CATALOG_URI_TAG = "{" + XML_CATALOG_XMLNS + "}uri"
XML_CATALOG_NAME_ATTR = "name"
XML_CATALOG_URI_ATTR = "uri"


def extract_target_namespace_from_xsd_schema(
    f: pathlib.Path, ignore_errors=True
) -> str | None:
    f = pathlib.Path(f)
    try:
        tree = ET.parse(f)
        root = tree.getroot()
        if root.tag == XSD_SCHEMA_TAG:
            tns = root.get(XSD_TARGET_NAMESPACE_ATTR)
            return tns
        else:
            if not ignore_errors:
                raise ValueError(f, root.tag)
    except ET.ParseError as e:
        if ignore_errors:
            pass
        else:
            raise ValueError(f) from e
    return None


def main():
    file_to_tns: dict[pathlib.Path, str] = {}
    for f in _files_from_path_list([pathlib.Path(a) for a in sys.argv[1:]]):
        tns = extract_target_namespace_from_xsd_schema(f)
        if tns is None:
            # TODO what about DTDs?
            pass
        else:
            file_to_tns[f] = tns

    ET.register_namespace("", XML_CATALOG_XMLNS)
    catalog = ET.Element(XML_CATALOG_CATALOG_TAG)
    # TODO handle collisions in target namespaces?
    for f, tns in file_to_tns.items():
        entry = ET.SubElement(catalog, XML_CATALOG_URI_TAG)
        entry.set(XML_CATALOG_NAME_ATTR, tns)
        entry.set(XML_CATALOG_URI_ATTR, f.as_uri())
    tree = ET.ElementTree(catalog)
    ET.indent(tree, space="    ")
    # TODO fix 'cp1252' showing up in xml decl
    tree.write(sys.stdout, encoding="unicode", xml_declaration=True)


def _files_from_path_list(
    plist: list[pathlib.Path],
) -> typing.Generator[pathlib.Path, None, None]:
    for p in plist:
        p = pathlib.Path(p)
        if p.is_dir():
            for c in p.iterdir():
                yield from _files_from_path_list([c])
        else:
            yield p


if __name__ == "__main__":
    if "--doctest" in sys.argv[1:]:
        doctest.testmod(optionflags=doctest.FAIL_FAST | doctest.ELLIPSIS)
    else:
        main()
