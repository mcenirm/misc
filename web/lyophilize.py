from __future__ import annotations

import argparse
import collections
import html.parser
import pathlib
import sys
import urllib.parse

import requests

try:
    import requests_cache

    _Session = requests_cache.CachedSession
except:
    _Session = requests.Session


# HTML attributes that carry resource URLs, keyed by tag name
_LINK_ATTRS: dict[str, str] = {
    "a": "href",
    "link": "href",
    "script": "src",
    "img": "src",
    "source": "src",
    "video": "src",
    "audio": "src",
    "iframe": "src",
}


class _LinkExtractor(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_name = _LINK_ATTRS.get(tag.lower())
        if attr_name:
            for name, value in attrs:
                if name == attr_name and value:
                    self.links.append(value)


def extract_links(base_url: str, html_text: str) -> list[str]:
    """Return absolute, fragment-stripped URLs found in html_text."""
    extractor = _LinkExtractor()
    extractor.feed(html_text)
    result = []
    for raw in extractor.links:
        absolute = urllib.parse.urljoin(base_url, raw)
        # Drop fragment so #section links don't create duplicate fetches
        absolute = urllib.parse.urldefrag(absolute).url
        result.append(absolute)
    return result


def same_origin(url_a: str, url_b: str) -> bool:
    a, b = urllib.parse.urlparse(url_a), urllib.parse.urlparse(url_b)
    return (a.scheme, a.netloc) == (b.scheme, b.netloc)


def url_to_local_path(dest: pathlib.Path, url: str) -> pathlib.Path:
    parsed = urllib.parse.urlparse(url)
    # Strip leading slash so joinpath doesn't treat it as absolute
    url_path = parsed.path.lstrip("/")
    local = dest / parsed.netloc / url_path
    # Treat directory-like paths (trailing slash or no suffix) as index.html
    if not url_path or url_path.endswith("/") or not local.suffix:
        local = local / "index.html"
    return local


def save_response(dest: pathlib.Path, url: str, content: bytes) -> pathlib.Path:
    local = url_to_local_path(dest, url)
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_bytes(content)
    return local


def freeze_dry(
    url_list_file: pathlib.Path,
    dest: pathlib.Path,
    session: requests.Session | None = None,
):
    url_list_file = pathlib.Path(url_list_file)
    dest = pathlib.Path(dest)
    if session is None:
        session = _Session()

    seed_urls = [
        line
        for line in [line.strip() for line in url_list_file.read_text().splitlines()]
        if line and not line.startswith("#")
    ]

    queue: collections.deque[str] = collections.deque(seed_urls)
    visited: set[str] = set()

    while queue:
        u = queue.popleft()
        if u in visited:
            continue
        visited.add(u)

        print("*", repr(u))
        response = session.get(u, allow_redirects=False)
        print(
            f"  Status: {response.status_code}  Content-Length: {len(response.content)}"
        )
        local = save_response(dest, u, response.content)
        print(f"  Saved:  {local}")

        content_type = response.headers.get("Content-Type", "")
        if "text/html" in content_type:
            links = extract_links(u, response.text)
            new_links = [
                link
                for link in links
                if link not in visited
                and any(same_origin(seed, link) for seed in seed_urls)
            ]
            if new_links:
                print(f"  Queued: {len(new_links)} new link(s)")
            queue.extend(new_links)


def main() -> int:
    ap = argparse.ArgumentParser()
    ud = ap.add_argument("--update-destination", action="store_true")
    ulf = ap.add_argument("url-list-file")
    dd = ap.add_argument("destination-dir")

    args: dict[str, str] = vars(ap.parse_args())
    update_destination = args[ud.dest]
    url_list_file = pathlib.Path(args[ulf.dest])
    destination_dir = pathlib.Path(args[dd.dest])

    if destination_dir.exists() and not update_destination:
        print(f"Destination exists, aborting: {destination_dir}", file=sys.stderr)
        return 1

    try:
        freeze_dry(url_list_file, destination_dir)
        return 0
    except (
        FileNotFoundError,
        requests.exceptions.RequestException,
    ) as e:
        print(e)

    return 1


if __name__ == "__main__":
    sys.exit(main())
