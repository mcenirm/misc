import enum
import sys
import xml.dom.pulldom
from functools import cache
from xml.dom.minidom import Node

import rich
from progress.bar import FillingSquaresBar

from mediawiki_export_filtering import copy_only_matching_pages
from mediawiki_export_reading import Page, opensesame


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


def wrangle(xmlinfile, xmloutfile, word_list):
    bar = FillingSquaresBar(max=len(word_list))

    def show_progress_and_true_if_title_in_word_list(page: Page) -> bool:
        b = page.title in word_list
        if b:
            bar.next()
        return b

    with bar, opensesame(xmlinfile) as inf, open(xmloutfile, "w") as outf:
        stats = copy_only_matching_pages(
            inf,
            outf,
            show_progress_and_true_if_title_in_word_list,
        )
    print()
    rich.print(len(word_list))
    rich.print(stats)


if __name__ == "__main__":
    from wordle_list import words

    wrangle(sys.argv[1], sys.argv[2], words)
