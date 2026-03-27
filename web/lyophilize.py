from __future__ import annotations

import pathlib
import sys

import requests
import requests_cache


def main():
    session = requests_cache.CachedSession()
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
        print(f"Final URL: {response.url}")
        print(f"Status Code: {response.status_code}")
        print(f"Content Length: {len(response.content)}")
        print(f"Text Length: {len(response.text)}")
        for k, v in response.headers.items():
            print("*", k, repr(v))


if __name__ == "__main__":
    main()
