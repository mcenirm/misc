import sys
from collections import defaultdict

import rich
from progress.counter import Counter

from mediawiki_export_reading import get_text_property, opensesame, page_elements

if __name__ == "__main__":
    childnamecounts = defaultdict(int)
    nscounts = defaultdict(int)
    prgrss = Counter()
    infname = sys.argv[1]
    inf = opensesame(infname, "r")
    with prgrss, inf:
        for elem in page_elements(inf):
            prgrss.next()
            title = get_text_property(elem, elem.namespaceURI, "title")
            ns = get_text_property(elem, elem.namespaceURI, "ns")
            title_prefix = title.split(":")[0] if title and ":" in title else ""
            nscounts[(ns, title_prefix)] += 1
            for child in elem.childNodes:
                if child.nodeType == child.ELEMENT_NODE:
                    name = child.localName
                    childnamecounts[name] += 1
    rich.print(childnamecounts)
    rich.print(nscounts)
