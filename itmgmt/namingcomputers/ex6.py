import sys
from collections import defaultdict
from typing import Any

import rich
from lxml import etree  # type:ignore
from progress.counter import Counter  # type:ignore

from mediawiki_export_constants import EXPORT_NS, NS, TITLE
from mediawiki_export_reading import get_text_property, opensesame, page_elements

if __name__ == "__main__":
    childnamecounts: dict[str, int] = defaultdict(int)
    nscounts: dict[tuple[str, str], int] = defaultdict(int)
    prgrss = Counter()
    infname = sys.argv[1]
    inf = opensesame(infname, "r")
    with prgrss, inf:
        for page_el in page_elements(inf):
            prgrss.next()
            title = get_text_property(page_el, EXPORT_NS, TITLE) or ""
            ns = get_text_property(page_el, EXPORT_NS, NS) or ""
            title_prefix = title.split(":")[0] if title and ":" in title else ""
            nscounts[(ns, title_prefix)] += 1
            for child in page_el:
                name = etree.QName(child).localname
                childnamecounts[name] += 1
    rich.print(childnamecounts)
    rich.print(nscounts)
