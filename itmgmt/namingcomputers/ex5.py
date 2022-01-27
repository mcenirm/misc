import sys

import rich
from progress.counter import Counter

from mediawiki_export_filtering import copy_only_matching_pages
from mediawiki_export_reading import Page, opensesame

if __name__ == "__main__":
    prgrss = Counter()

    def match_parts_of_speech_and_update_counter(page: Page) -> bool:
        prgrss.next()
        return page.text and "[[Category:en:Parts of speech]]" in page.text

    with prgrss, opensesame(sys.argv[1]) as inf, open(sys.argv[2], "w") as outf:
        stats = copy_only_matching_pages(
            inf,
            outf,
            match_parts_of_speech_and_update_counter,
        )
    print()
    rich.print(stats)