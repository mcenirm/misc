# TODO (maybe)
# * do not keep old revisions of artifacts
# * extract important details from artifacts and store in a history
# * generate report showing changes of important details


from __future__ import annotations

import configparser
import dataclasses
import datetime
import json
import pathlib
import re
import shutil
import time
import urllib.parse
import urllib.request

import bs4
from icecream import ic
from rich import inspect as ri

DEFAULT_LOCAL_SETTINGS_PATH = pathlib.Path("local-settings.ini")


DEFAULT_LOCAL_SETTINGS_TEMPLATE = """
[settings]
web = <url to web site>
downloads = <path to downloads folder>
"""


@dataclasses.dataclass(kw_only=True, frozen=True)
class Artifact:
    url: str
    download_name: str = ""
    ext: str = ".html"

    def __post_init__(self):
        if self.download_name == "":
            guess = guess_download_name_from_url2(url=self.url, ext=self.ext)
            if guess is None:
                raise ValueError("unable to guess download name for url", self.url)
            object.__setattr__(self, "download_name", guess)


def guess_download_name_from_url(*, url: str, ext=".html") -> str | None:
    """

    >>> guess_download_name_from_url(url=None)
    >>> guess_download_name_from_url(url="data:text/plain,test%20text%0D%0A")
    >>> guess_download_name_from_url(url="https://example.com/")
    'example.com.html'
    >>> guess_download_name_from_url(url="https://example.com/file.txt")
    'file.txt'
    >>> guess_download_name_from_url(url="https://example.com/path/file.txt")
    'file.txt'
    >>> guess_download_name_from_url(url="https://example.com/search?")
    'example.com--search.html'
    >>> guess_download_name_from_url(url="https://example.com/search?q=a%20b")
    'example.com--search--q=a%20b.html'
    >>> guess_download_name_from_url(url="https://example.com/api/search?q=a%20b")
    'example.com--api--search--q=a%20b.html'
    >>> guess_download_name_from_url(url="https://example.com/api/search.json?q=a%20b")
    'example.com--api--search--q=a%20b.json'

    """

    parsed = urllib.parse.urlparse(url=url, allow_fragments=True)
    if url is None or parsed.scheme == "data":
        return None
    if parsed.hostname and (parsed.path or "/") == "/" and not parsed.query:
        return parsed.hostname + ext
    guess = pathlib.PurePosixPath(parsed.path)
    if guess.suffix and not parsed.query:
        return guess.name
    suffix, guess = (guess.suffix or ext), guess.with_suffix("")
    guess = parsed.hostname + str(guess).replace("/", "--")
    if parsed.query:
        guess += "--" + parsed.query
    guess += suffix
    return guess


def guess_download_name_from_url2(*, url: str, ext: str | None = None) -> str | None:
    """

    >>> guess_download_name_from_url2(url=None)
    >>> guess_download_name_from_url2(url="data:text/plain,test%20text%0D%0A")
    >>> guess_download_name_from_url2(url="https://example.com/")
    'example.com.html'
    >>> guess_download_name_from_url2(url="https://example.com/file.txt")
    'example.com/file.txt'
    >>> guess_download_name_from_url2(url="https://example.com/path/file.txt")
    'example.com/path/file.txt'
    >>> guess_download_name_from_url2(url="https://example.com/path/")
    'example.com/path.html'
    >>> guess_download_name_from_url2(url="https://example.com/search?")
    'example.com/search.html'
    >>> guess_download_name_from_url2(url="https://example.com/search?q=a%20b")
    'example.com/search--q=a%20b.html'
    >>> guess_download_name_from_url2(url="https://example.com/api/search?q=a%20b")
    'example.com/api/search--q=a%20b.html'
    >>> guess_download_name_from_url2(url="https://example.com/api/search.json?q=a%20b")
    'example.com/api/search--q=a%20b.json'

    """

    parsed = urllib.parse.urlparse(url=url, allow_fragments=True)
    if url is None or parsed.scheme == "data":
        return None
    path = pathlib.PurePosixPath(parsed.path.removeprefix("/"))
    suffix = path.suffix
    if suffix:
        path = path.with_suffix("")
    path = pathlib.PurePosixPath(parsed.hostname) / path
    guess = str(path)
    if parsed.query:
        guess += "--" + parsed.query
    if suffix and ext is None:
        guess += suffix
    elif ext is None:
        guess += ".html"
    elif ext and ext != suffix:
        guess += ext
    return guess


def refresh_local_settings(
    *,
    configfile: pathlib.Path = DEFAULT_LOCAL_SETTINGS_PATH,
    template: str = DEFAULT_LOCAL_SETTINGS_TEMPLATE,
):
    r"""

    >>> from pathlib import Path
    >>> from tempfile import TemporaryDirectory

    >>> with TemporaryDirectory() as tmpdir:
    ...     ini = Path(tmpdir) / "test.ini"
    ...     refresh_local_settings(configfile=ini)
    ...     with ini.open() as f:
    ...         assert f.read().strip() == DEFAULT_LOCAL_SETTINGS_TEMPLATE.strip()
    ...

    >>> with TemporaryDirectory() as tmpdir:
    ...     template, original, expected = (
    ...         "[test]\nfoo = <foo>\nbar = 2\n\n",
    ...         "[test]\nfoo = 1\n\n",
    ...         "[test]\nfoo = 1\nbar = 2\n\n",
    ...     )
    ...     ini = Path(tmpdir) / "test.ini"
    ...     with ini.open("w") as f:
    ...         _ = f.write(original)
    ...     refresh_local_settings(configfile=ini, template=template)
    ...     with ini.open() as f:
    ...         actual = f.read()
    ...     assert actual == expected, f"{actual!r} != {expected!r}"
    ...

    """

    if not configfile.exists():
        with configfile.open("w") as f:
            f.write(template)
        return

    cp = configparser.ConfigParser()
    cp.read_string(template, source="<template>")
    cp.read(configfile)
    with configfile.open("w") as f:
        cp.write(f)


def retrieve(
    *,
    url: str,
    download_to: pathlib.Path,
    unless_too_recent=datetime.timedelta(minutes=60),
) -> pathlib.Path:
    r"""

    >>> from pathlib import Path
    >>> from tempfile import TemporaryDirectory
    >>> from urllib.parse import quote

    >>> with TemporaryDirectory() as tmpdir:
    ...     exp_data = "test\n"
    ...     url = "data:text/plain," + quote(exp_data)
    ...     exp_path = Path(tmpdir) / "test.txt"
    ...     act_path = retrieve(url=url, download_to=exp_path)
    ...     assert act_path.exists(), f"{act_path!r} does not exist"
    ...     assert act_path == exp_path, f"{act_path!r} != {exp_path!r}"
    ...     with act_path.open() as f:
    ...         act_data = f.read()
    ...     assert act_data == exp_data, f"{act_data!r} != {exp_data!r}"
    ...

    """

    if unless_too_recent:
        if download_to.is_file() and file_age(download_to) < unless_too_recent:
            return download_to

    download_to.parent.mkdir(parents=True, exist_ok=True)

    try:
        tmp, msg = urllib.request.urlretrieve(url=url)
        ic(msg.items())
        real_downloaded_to = pathlib.Path(shutil.copy2(tmp, download_to))
    finally:
        urllib.request.urlcleanup()
    return real_downloaded_to


def file_age(path: pathlib.Path) -> datetime.timedelta:
    return datetime.timedelta(seconds=time.time() - path.stat().st_mtime)


class LWR:
    def __init__(self, soup: bs4.BeautifulSoup):
        self.soup = soup
        self.base_path = self.extract_lwr_base_path()
        self.routes = self.extract_routes()
        self.views = self.extract_views_mapping()

    def is_lwr_app(self) -> bool:
        # 1. Check for the LWR custom root DOM element
        if self.soup.find("webruntime-app"):
            return True

        # 2. Check <script> tags for LWR runtime module imports or endpoints
        script_src_pattern = re.compile(
            r"(/lwr/|/webruntime/|@app/|@salesforce/)", re.IGNORECASE
        )
        for script in self.soup.find_all("script", src=True):
            if script_src_pattern.search(script["src"]):
                return True

        # 3. Check inline <script> tags for LWR module initializations
        # Matches LWR.define, window.LWR, window.LWR_LOADER, or LWR.provide
        inline_pattern = re.compile(
            r"(?:window\s*\.\s*LWR(?:_LOADER)?|LWR\s*\.\s*(?:define|provide|config))\s*\(",
            re.IGNORECASE,
        )
        for script in self.soup.find_all("script", src=False):
            if script.string and inline_pattern.search(script.string):
                return True

        return False

    def extract_lwr_base_path(self) -> str | None:
        # 1. Matches LWR.define('@app/basePath', [], function() { return '/site/s'; })
        # Accepts string primitives or object returns containing basePath
        base_path_pattern = re.compile(
            r"\bLWR\.define\s*\(\s*['\"]@app/basePath['\"]\s*,\s*\[\]\s*,\s*function\s*\(\)\s*\{\s*return\s*['\"](|/[^'\"]+)['\"]\s*;\s*\}\s*\)",
            re.IGNORECASE,
        )

        # 2. Matches LWR.define('@app/context', ...) or window.LWR object structure
        context_pattern = re.compile(
            r"LWR\.define\s*\(\s*['\"]@app/context['\"]\s*,\s*\[\]\s*,\s*function\s*\(\)\s*\{\s*return\s*(\{.*?\}|\{.*\})\s*;\s*\}\s*\)",
            re.DOTALL,
        )
        lwr_obj_pattern = re.compile(
            r"window\.LWR\s*=\s*window\.LWR\s*\|\|\s*(\{.*?\});", re.DOTALL
        )

        for script in self.soup.find_all("script", src=False):
            if not script.string:
                continue

            # Check @app/basePath module
            base_match = base_path_pattern.search(script.string)
            if base_match:
                return base_match.group(1)

            # Check @app/context module
            ctx_match = context_pattern.search(script.string)
            if ctx_match:
                try:
                    data = json.loads(ctx_match.group(1))
                    if "basePath" in data:
                        return data["basePath"]
                except json.JSONDecodeError:
                    pass

            # Check window.LWR script object
            lwr_match = lwr_obj_pattern.search(script.string)
            if lwr_match:
                try:
                    data = json.loads(lwr_match.group(1))
                    if "basePath" in data:
                        return data["basePath"]
                except json.JSONDecodeError:
                    pass

        # 3. Fallback: Parse root element attributes
        app_element = self.soup.find("webruntime-app")
        if app_element and app_element.has_attr("data-base-path"):
            return app_element["data-base-path"]

        return None

    def extract_routes(self) -> list[dict] | None:
        # Pattern matching LWR.define('@app/routes', ...) structure
        pattern = re.compile(
            r"LWR\.define\s*\(\s*['\"]@app/routes['\"]\s*,\s*\[\]\s*,\s*function\s*\(\)\s*\{\s*return\s*(\[.*?\])\s*;\s*\}\s*\)",
            re.DOTALL,
        )

        # Inspect all inline script tags
        for script in self.soup.find_all("script", src=False):
            if not script.string:
                continue

            match = pattern.search(script.string)
            if match:
                raw_json_array = match.group(1)
                try:
                    # Parse the extracted JSON route array
                    return json.loads(raw_json_array)
                except json.JSONDecodeError:
                    # Handle cases where keys/strings use single quotes or unquoted keys
                    cleaned_json = re.sub(r"'", '"', raw_json_array)
                    return json.loads(cleaned_json)

        return None

    def extract_views_mapping(self) -> dict[str, str] | None:
        pattern = re.compile(r"['\"]@view/(\w+)['\"]\s*:\s*['\"]([^'\"]+)['\"]\s*[,}]")

        for script in self.soup.find_all("script", src=False):
            if not script.string:
                continue

            views = {m.group(1): m.group(2) for m in pattern.finditer(script.string)}
            if views:
                return views

        return None

    def get_app_relative_path(self, url_or_path: str) -> str:
        parts = urllib.parse.urlsplit(url_or_path)
        return parts.path.removeprefix(self.base_path)

    def match_route(self, url_path: str) -> dict | None:
        url_path = self.get_app_relative_path(url_path)
        for route in self.routes:
            route_pattern = route.get("path")
            if not route_pattern:
                continue

            # Convert Express-style params (:id -> named group, * -> wildcard)
            regex_pattern = re.sub(r":(\w+)", r"(?P<\1>[^/]+)", route_pattern)
            regex_pattern = re.sub(r"\*", r".*", regex_pattern)
            regex = f"^{regex_pattern}$"

            if re.match(regex, url_path):
                return route

        return None


def main() -> None:
    refresh_local_settings()
    cp = configparser.ConfigParser()
    cp.read(DEFAULT_LOCAL_SETTINGS_PATH)
    settings = dict(cp["settings"])
    ic(settings)
    web = settings["web"]
    downloads = pathlib.Path(settings["downloads"])
    downloads.mkdir(exist_ok=True, parents=True)
    web_artifact = Artifact(url=web)
    ic(web_artifact)
    web_copy = retrieve(url=web, download_to=downloads / web_artifact.download_name)
    ic(web_copy, web_copy.stat())
    soup = bs4.BeautifulSoup(web_copy.read_bytes(), "html5lib")
    ic(repr(str(soup.html.body))[:80])
    lwr = LWR(soup)
    current_route = lwr.match_route(web_artifact.url)
    current_view = lwr.views[current_route["view"]]
    ic(current_route)
    ic(current_view)
    view = Artifact(
        url=urllib.parse.urljoin(web_artifact.url, lwr.base_path + current_view),
        ext=".json",
    )
    ic(view)
    view_copy = retrieve(url=view.url, download_to=downloads / view.download_name)
    ic(view_copy, view_copy.stat())


if __name__ == "__main__":
    import doctest

    failure_count, test_count = doctest.testmod(optionflags=doctest.FAIL_FAST)
    if not failure_count:
        main()
