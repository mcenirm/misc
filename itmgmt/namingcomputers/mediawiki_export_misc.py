import sys
from mediawiki_export_reading import opensesame, pages_as_dicts
from progress import Progress
from progress.counter import Counter
import rich


def count_pages(prgrss: Progress, inf, /):
    count = 0
    with prgrss, inf:
        for page in pages_as_dicts(inf):
            prgrss.next()
            count += 1
    rich.print(count)


if __name__ == "__main__":
    infname = sys.argv[1]
    funcname = sys.argv[2]
    prgrss = Counter()
    func = locals()[funcname]
    inf = opensesame(infname, "r")
    func(prgrss, inf)
