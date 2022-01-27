import bz2
import xml.dom.pulldom
from dataclasses import dataclass
from functools import cache
from typing import Iterator, Optional, cast
from xml.dom.minidom import Element, Node

from mediawiki_export_constants import EXPORT_NS, FORMAT, MODEL, PAGE, TEXT, TITLE


@dataclass
class Page:
    title: str
    model: str
    format: str
    text: str


def opensesame(*args, **kwargs):
    try:
        f = bz2.open(*args, **kwargs)
        f.peek(0)
        return f
    except OSError as e:
        if e.args != ("Invalid data stream",):
            raise
    return open(*args, **kwargs)


@cache
def get_text_property(
    element: Element,
    property_uri: str,
    property_local_name: str,
) -> Optional[str]:
    node_list = element.getElementsByTagNameNS(property_uri, property_local_name)
    if not node_list:
        return None
    property_element = node_list.item(0)
    if not property_element:
        return None
    text_node = property_element.firstChild
    if not text_node:
        return None
    if text_node.nodeType != Node.TEXT_NODE:
        return None
    text_node.normalize()
    return text_node.wholeText


def always_true(*args):
    return True


def pages(
    xmlfile,
    /,
    matcher=always_true,
    *,
    purge_discarded_nodes=True,
) -> Iterator[Page]:
    for page_elem in page_elements(xmlfile):
        title = get_text_property(page_elem, EXPORT_NS, TITLE)
        model = get_text_property(page_elem, EXPORT_NS, MODEL)
        format_ = get_text_property(page_elem, EXPORT_NS, FORMAT)
        text = get_text_property(page_elem, EXPORT_NS, TEXT)
        page = Page(title, model, format_, text)
        if matcher(page):
            yield page
        elif purge_discarded_nodes:
            if page_elem.parentNode:
                page_elem.parentNode.removeChild(page_elem)
            page_elem.unlink()


def page_elements(xmlfile) -> Iterator[Element]:
    docstream = xml.dom.pulldom.parse(xmlfile)
    for event, node in docstream:
        node = cast(Node, node)
        if (
            event == xml.dom.pulldom.START_ELEMENT
            and node.namespaceURI == EXPORT_NS
            and node.localName == PAGE
        ):
            page_element = cast(Element, node)
            docstream.expandNode(page_element)
            yield page_element
