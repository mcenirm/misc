import sys

import rich
from progress.counter import Counter  # type: ignore

from mediawiki_export_filtering import copy_only_matching_pages
from mediawiki_export_reading import Page, opensesame

if __name__ == "__main__":
    prgrss = Counter()

    def match_parts_of_speech_and_update_counter(page: Page) -> bool:
        prgrss.next()
        if not page.text:
            return False
        return "[[Category:en:Parts of speech]]" in page.text

    inf = opensesame(sys.argv[1], "r")
    outf = open(sys.argv[2], "w", encoding="utf-8")
    with prgrss, inf, outf:
        stats = copy_only_matching_pages(
            inf,
            outf,
            match_parts_of_speech_and_update_counter,
        )
    print()
    rich.print(stats)
