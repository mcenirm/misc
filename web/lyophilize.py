from __future__ import annotations

import collections
import html.parser
import pathlib
import sys
import urllib.parse

try:
    import requests_cache

    Session = requests_cache.CachedSession
except:
    import requests

    Session = requests.Session

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


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <url-list-file> <destination-dir>", file=sys.stderr)
        sys.exit(1)

    dest = pathlib.Path(sys.argv[2])
    session = Session()

    seed_urls = [
        line
        for line in [
            line.strip() for line in pathlib.Path(sys.argv[1]).read_text().splitlines()
        ]
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
        print(f"  Status: {response.status_code}  Content-Length: {len(response.content)}")
        local = save_response(dest, u, response.content)
        print(f"  Saved:  {local}")

        content_type = response.headers.get("Content-Type", "")
        if "text/html" in content_type:
            links = extract_links(u, response.text)
            new_links = [
                link for link in links
                if link not in visited and any(same_origin(seed, link) for seed in seed_urls)
            ]
            if new_links:
                print(f"  Queued: {len(new_links)} new link(s)")
            queue.extend(new_links)


if __name__ == "__main__":
    main()
