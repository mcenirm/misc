from __future__ import annotations

import pathlib
import sys
import urllib.parse

try:
    import requests_cache

    Session = requests_cache.CachedSession
except:
    import requests

    Session = requests.Session


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
    urllist = [
        line
        for line in [
            line.strip() for line in pathlib.Path(sys.argv[1]).read_text().splitlines()
        ]
        if line and not line.startswith("#")
    ]
    for u in urllist:
        print("*", repr(u))
        response = session.get(u, allow_redirects=False)
        print(f"  Status: {response.status_code}  Content-Length: {len(response.content)}")
        local = save_response(dest, u, response.content)
        print(f"  Saved:  {local}")


if __name__ == "__main__":
    main()
