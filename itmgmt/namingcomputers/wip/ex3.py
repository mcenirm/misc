import enum
import sys
import xml.dom.pulldom
from dataclasses import dataclass
from functools import cache
from logging import warning
from typing import Union
from xml.dom.minidom import Element, Node

from rich import print as rprint

from mediawiki_export_util import EXPORT_NS, FORMAT, MODEL, PAGE, SKIPS, TEXT, TITLE


class NodeType(enum.Enum):
    ELEMENT_NODE = Node.ELEMENT_NODE
    ATTRIBUTE_NODE = Node.ATTRIBUTE_NODE
    TEXT_NODE = Node.TEXT_NODE
    CDATA_SECTION_NODE = Node.CDATA_SECTION_NODE
    ENTITY_REFERENCE_NODE = Node.ENTITY_REFERENCE_NODE
    ENTITY_NODE = Node.ENTITY_NODE
    PROCESSING_INSTRUCTION_NODE = Node.PROCESSING_INSTRUCTION_NODE
    COMMENT_NODE = Node.COMMENT_NODE
    DOCUMENT_NODE = Node.DOCUMENT_NODE
    DOCUMENT_TYPE_NODE = Node.DOCUMENT_TYPE_NODE
    DOCUMENT_FRAGMENT_NODE = Node.DOCUMENT_FRAGMENT_NODE
    NOTATION_NODE = Node.NOTATION_NODE


@dataclass
class Page:
    title: str
    model: str
    format: str
    text: str


EVENTS_TO_HIDE = set(
    [
        xml.dom.pulldom.START_DOCUMENT,
        xml.dom.pulldom.END_ELEMENT,
        xml.dom.pulldom.CHARACTERS,
    ]
)


@cache
def stack(node: Node) -> list[str]:
    return (stack(node.parentNode) + [node]) if node else []


@cache
def get_text_property(
    element: Element,
    property_uri: str,
    property_local_name: str,
) -> Union[str, None]:
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
    for node in page_nodes(xmlfile, title_filter):
        title = get_text_property(node, EXPORT_NS, TITLE)
        model = get_text_property(node, EXPORT_NS, MODEL)
        format_ = get_text_property(node, EXPORT_NS, FORMAT)
        text = get_text_property(node, EXPORT_NS, TEXT)
        rprint({"title": title})


def read_page_nodes(xmlfile):
    docstream = xml.dom.pulldom.parse(xmlfile)
    for event, node in docstream:
        if (
            event == xml.dom.pulldom.START_ELEMENT
            and node.namespaceURI == EXPORT_NS
            and node.localName == PAGE
        ):
            docstream.expandNode(node)
            yield node


def filter_pages_by_title(xmlfile, title_filter=default_title_filter):
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


def wrangle(xmlfile, word_list):
    def title_in_word_list(title: str) -> bool:
        return title in word_list

    for i, page in enumerate(pages(xmlfile, title_in_word_list)):
        rprint(page.title)
        if i >= 10:
            break


if __name__ == "__main__":
    from wordle_list import word_list

    wrangle(sys.argv[1], word_list)
