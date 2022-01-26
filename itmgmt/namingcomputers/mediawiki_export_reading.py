import bz2
import xml.dom.pulldom
from dataclasses import dataclass
from functools import cache
from typing import Optional
from xml.dom.minidom import Element, Node

from mediawiki_export_constants import (
    EXPORT_NS,
    FORMAT,
    MEDIAWIKI,
    MODEL,
    PAGE,
    TEXT,
    TITLE,
)


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
    property_element = node_list.item(0)
    if not property_element:
        return None
    text_node = property_element.firstChild
    if text_node.nodeType != Node.TEXT_NODE:
        return None
    text_node.normalize()
    return text_node.wholeText


def default_title_filter(title: str) -> bool:
    return True


def pages(xmlfile, title_filter=default_title_filter):
    for node in filter_pages_by_title(xmlfile, title_filter):
        title = get_text_property(node, EXPORT_NS, TITLE)
        model = get_text_property(node, EXPORT_NS, MODEL)
        format_ = get_text_property(node, EXPORT_NS, FORMAT)
        text = get_text_property(node, EXPORT_NS, TEXT)
        page = Page(title, model, format_, text)
        yield page


def filter_pages_by_title(
    xmlfile,
    title_filter=default_title_filter,
    purge_other_pages=True,
):
    # TODO - refactor to be more general page filter, not just title
    docstream = xml.dom.pulldom.parse(xmlfile)
    for event, node in docstream:
        if (
            event == xml.dom.pulldom.START_ELEMENT
            and node.namespaceURI == EXPORT_NS
            and node.localName == PAGE
        ):
            docstream.expandNode(node)
            title = get_text_property(node, EXPORT_NS, TITLE)
            if title_filter(title):
                yield node
            elif purge_other_pages:
                node.parentNode.removeChild(node)
