import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from typing import Callable, TextIO

from mediawiki_export_constants import (
    EXPORT_NS,
    FORMAT,
    MEDIAWIKI,
    MODEL,
    PAGE,
    TEXT,
    TITLE,
)
from mediawiki_export_reading import Page, pages


@dataclass
class StatisticsAboutCopiedPages:
    pages_seen: int
    pages_copied: int
    pages_discarded: int


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

    # This block of elements gets reused to avoid memory issues.
    # The root element provides the xmlns, so these do not need it.
    outpage = ElementTree.Element(PAGE)
    outtitle = ElementTree.SubElement(outpage, TITLE)
    outmodel = ElementTree.SubElement(outpage, MODEL)
    outformat = ElementTree.SubElement(outpage, FORMAT)
    outtext = ElementTree.SubElement(outpage, TEXT)
    outtree = ElementTree.ElementTree(outpage)
    ElementTree.indent(outtree)
    outfile.write(f'<{MEDIAWIKI} xmlns="{EXPORT_NS}">')
    try:
        for page in pages(infile, stats_tracking_matcher):
            if page.model != "wikitext":
                raise ValueError(f"unknown model {page.model!r} for {page.title!r}")
            if page.format != "text/x-wiki":
                raise ValueError(f"unknown format {page.format!r} for {page.title!r}")
            outtitle.text = page.title
            outmodel.text = page.model
            outformat.text = page.format
            outtext.text = page.text
            outtree.write(
                outfile,
                encoding="unicode",
                xml_declaration=False,
                default_namespace=None,
                method="xml",
                short_empty_elements=True,
            )
    finally:
        outfile.write(f"</{MEDIAWIKI}>")
    return stats
