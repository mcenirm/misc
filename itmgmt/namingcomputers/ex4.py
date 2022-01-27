import collections
import sys

import rich
import wikitextparser as wtp
from icecream import ic

from mediawiki_export_reading import opensesame, pages
from wiktionary_export_reading import language_sections


if __name__ == "__main__":
    with opensesame(sys.argv[1]) as f:
        counts = collections.defaultdict(int)
        for page_num, page in enumerate(pages(f), 1):
            for language_section in language_sections(page, "English"):
                for i, s in enumerate(language_section.sections, 1):
                    if s.level > 2:
                        counts[s.title] += 1
                        # rich.print(f"{page_num:4}  {i:4} {' '*s.level} {s.title}")
        top_counts = dict(
            sorted(counts.items(), key=lambda item: item[1], reverse=True)[:30]
        )
        rich.print(top_counts)
