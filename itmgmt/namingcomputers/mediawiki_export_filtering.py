from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, TextIO

from lxml import etree  # type: ignore

from mediawiki_export_constants import FORMAT, MODEL, PAGE, TEXT, TITLE
from mediawiki_export_reading import QMEDIAWIKI, Page, page_elements, pages


@dataclass
class StatisticsAboutCopiedPages:
    pages_seen: int
    pages_copied: int
    pages_discarded: int


@dataclass
class StatisticsAboutPartitionedPages:
    pages_seen: int = 0
    pages_copied_by_outf_name: dict[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )


class PageTreeWrapper:
    """A reusable ElementTree wrapper representing a mediawiki export page"""

    def __init__(self) -> None:
        self.outpage = etree.ElementTree.Element(PAGE)
        self.outtitle = etree.ElementTree.SubElement(self.outpage, TITLE)
        self.outmodel = etree.ElementTree.SubElement(self.outpage, MODEL)
        self.outformat = etree.ElementTree.SubElement(self.outpage, FORMAT)
        self.outtext = etree.ElementTree.SubElement(self.outpage, TEXT)
        self.outtree = etree.ElementTree.ElementTree(self.outpage)
        etree.ElementTree.indent(self.outtree)

    def reset(self, page: Page) -> None:
        if page.model != "wikitext":
            raise ValueError(f"unknown model {page.model!r} for {page.title!r}")
        if page.format != "text/x-wiki":
            raise ValueError(f"unknown format {page.format!r} for {page.title!r}")
        self.outtitle.text = page.title
        self.outmodel.text = page.model
        self.outformat.text = page.format
        self.outtext.text = page.text

    def write(self, *args, **kwargs) -> None:
        self.outtree.write(*args, **kwargs)


def copy_only_matching_pages(
    infile: TextIO,
    outfile: TextIO,
    matcher=Callable[[Page], bool],
    /,
) -> StatisticsAboutCopiedPages:
    stats = StatisticsAboutCopiedPages(0, 0, 0)

    def stats_tracking_matcher(page: Page) -> bool:
        b = matcher(page)
        if b:
            stats.pages_copied += 1
        else:
            stats.pages_discarded += 1
        stats.pages_seen += 1
        return b

    with etree.xmlfile(outfile) as xmlout:
        with xmlout.element(QMEDIAWIKI):
            for page in pages(infile, stats_tracking_matcher):
                xmlout.write(page.to_lxml_etree_element())
    return stats


def partition_pages_xml(
    inf: TextIO,
    outfswitcher: Callable[[etree.Element], tuple[str, TextIO]],
) -> StatisticsAboutPartitionedPages:
    stats = StatisticsAboutPartitionedPages()
    outfs_by_name: dict[str, TextIO] = {}
    for page in page_elements(inf):
        stats.pages_seen += 1
        name, outf = outfswitcher(page)
        stats.pages_copied_by_outf_name[name] += 1
    return stats
