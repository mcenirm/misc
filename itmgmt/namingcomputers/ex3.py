import enum
import sys
import xml.dom.pulldom
import xml.etree.ElementTree as ElementTree
from functools import cache
from xml.dom.minidom import Node

from progress.bar import FillingSquaresBar

from mediawiki_export_constants import (
    EXPORT_NS,
    FORMAT,
    MEDIAWIKI,
    MODEL,
    PAGE,
    TEXT,
    TITLE,
)
from mediawiki_export_reading import opensesame, pages


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
    def title_in_word_list(title: str) -> bool:
        return title in word_list

    bar = FillingSquaresBar(max=len(word_list))

    with opensesame(xmlinfile) as inf, open(xmloutfile, "w") as outf:
        i = 0
        outpage = ElementTree.Element(PAGE)
        outtitle = ElementTree.SubElement(outpage, TITLE)
        outmodel = ElementTree.SubElement(outpage, MODEL)
        outformat = ElementTree.SubElement(outpage, FORMAT)
        outtext = ElementTree.SubElement(outpage, TEXT)
        outtree = ElementTree.ElementTree(outpage)
        ElementTree.indent(outtree)
        outf.write('<{0} xmlns="{1}">'.format(MEDIAWIKI, EXPORT_NS))
        try:
            for page in pages(inf, title_in_word_list):
                i += 1
                if page.model != "wikitext":
                    raise ValueError(
                        "unexpected model {0:r} for {1:r}".format(
                            page.model, page.title
                        )
                    )
                if page.format != "text/x-wiki":
                    raise ValueError(
                        "unexpected format {0:r} for {1:r}".format(
                            page.format, page.title
                        )
                    )
                outtitle.text = page.title
                outmodel.text = page.model
                outformat.text = page.format
                outtext.text = page.text
                outtree.write(
                    outf,
                    encoding="unicode",
                    xml_declaration=False,
                    default_namespace=None,
                    method="xml",
                    short_empty_elements=True,
                )
                bar.next()
        finally:
            bar.finish()
            outf.write("</{0}>".format(MEDIAWIKI))
        print()
        print("{0} out of {1} words".format(i, len(word_list)))


if __name__ == "__main__":
    from wordle_list import words

    wrangle(sys.argv[1], sys.argv[2], words)
