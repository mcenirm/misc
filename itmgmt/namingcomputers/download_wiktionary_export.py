"""Download Wiktionary dump file"""


import sys
import urllib.parse
from contextlib import AbstractContextManager
from dataclasses import dataclass
from logging import warning
from math import ceil
from pathlib import Path
from typing import Callable
from urllib.request import urlretrieve

import bs4
import requests
import requests_cache
import rich
from progress import Progress
from progress.bar import FillingSquaresBar

ENWIKTIONARY_DUMPS_TOP = "https://dumps.wikimedia.org/enwiktionary/"
ENWIKTIONARY_DUMPS_OUT = Path() / "enwiktionary"


@dataclass
class Link:
    href: str
    text: str
    full_url: str


def determine_best_dump_date_link(links: list[Link], **kwargs) -> Link:
    if len(links) == 1:
        return links[0]
    rich.inspect(links)
    raise NotImplementedError


def determine_best_download_link(links: list[Link], **kwargs) -> Link:
    if len(links) == 1:
        return links[0]
    scores = {_.href: 0 for _ in links}
    for link in links:
        href = link.href
        if href == "../":
            scores[href] -= 100
        if href.find("-current") > -1:
            scores[href] += 10
    best_link = sorted(
        links,
        key=lambda link: scores[link.href],
        reverse=True,
    )[0]
    return best_link


def find_links(url: str, *, find_all_kwargs: dict = {}) -> list[Link]:
    response = requests.get(url)
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    anchors = soup.find_all("a", **find_all_kwargs)
    links = []
    for anchor in anchors:
        href = anchor["href"]
        text = anchor.text
        full_url = urllib.parse.urljoin(url, href)
        link = Link(href, text, full_url)
        links.append(link)
    return links


def determine_dump_date_url(
    *,
    top_url: str = ENWIKTIONARY_DUMPS_TOP,
    dump_date_link_filter: Callable = None,
    dump_date: str = "latest",
    **kwargs,
) -> str:
    links = find_links(top_url)
    if not dump_date_link_filter:
        dump_date_href = dump_date + "/"
        dump_date_link_filter = lambda link: link.href == dump_date_href
    links = [_ for _ in links if dump_date_link_filter(_)]
    best_link = determine_best_dump_date_link(links, **kwargs)
    return best_link.full_url


class ProgressReportHook(AbstractContextManager):
    """Use progress.Progress as urlretrieve reporthook"""

    def __init__(
        self,
        message="Retrieving",
        progress_class: Progress = FillingSquaresBar,
    ) -> None:
        self.message = message
        self.progress_class = progress_class
        self.progress = None

    def __call__(
        self,
        blocks_so_far: int,
        block_size_in_bytes: int,
        total_size_in_bytes: int,
    ) -> None:
        if not self.progress:
            progress_max = int(ceil(total_size_in_bytes / block_size_in_bytes))
            self.progress = self.progress_class(self.message, max=progress_max)
        self.progress.next()

    def __exit__(self, __exc_type, __exc_value, __traceback) -> bool:
        self.finish()
        return False

    def finish(self):
        self.progress.finish()
        self.progress = None


def download(
    url,
    *,
    out_file: Path = None,
    out_dir: Path = ENWIKTIONARY_DUMPS_OUT,
    **kwargs,
) -> Path:
    if not out_file:
        out_file = out_dir / Path(urllib.parse.urlparse(url).path).name
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with ProgressReportHook() as hook:
        local_filename, headers = urlretrieve(url, out_file, reporthook=hook)
    if not out_file.samefile(local_filename):
        warning(
            "download moved: expected=%r, result=%r",
            str(out_file),
            str(local_filename),
        )
    return out_file


def determine_download_url(*, dump_date_url: str = None, **kwargs) -> str:
    if not dump_date_url:
        dump_date_url = determine_dump_date_url(**kwargs)
    links = find_links(dump_date_url)
    best_link = determine_best_download_link(links, **kwargs)
    return best_link.full_url


def run(*, download_url: str = None, **kwargs):
    if not download_url:
        download_url = determine_download_url(**kwargs)
    out_file = download(download_url, **kwargs)
    print(out_file)


def parse_argv(argv: list[str]) -> dict:
    """TODO actually parse argv to get settings"""
    return {}


def main() -> None:
    kwargs = parse_argv(sys.argv)
    run(**kwargs)
    sys.exit(0)


if __name__ == "__main__":
    requests_cache.install_cache(use_cache_dir=True)
    main()
