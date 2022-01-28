from typing import Iterator

import wikitextparser as wtp  # type: ignore

from mediawiki_export_constants import WIKITEXT_FORMAT, WIKITEXT_MODEL
from mediawiki_export_reading import Page

LANGUAGE_SECTION_LEVEL = 2


def language_sections(page: Page, /, match_title: str = None) -> Iterator[wtp.Section]:
    if page.model != WIKITEXT_MODEL:
        raise ValueError(
            "expected wikitext model %r but got %r", WIKITEXT_MODEL, page.model
        )
    if page.format != WIKITEXT_FORMAT:
        raise ValueError(
            "expected wikitext format %r but got %r", WIKITEXT_FORMAT, page.format
        )

    if match_title:
        title_matches = lambda s: s.title == match_title
    else:
        title_matches = lambda s: True
    wikitext = wtp.parse(page.text)
    for section in wikitext.sections:
        if section.level == LANGUAGE_SECTION_LEVEL and title_matches(section):
            yield section
