from __future__ import annotations

import dataclasses as _dataclasses
import pathlib as _pathlib

from icecream import ic
from rich import inspect as ri

DEFAULT_LOCAL_SETTINGS_PATH = _pathlib.Path("local-settings.ini")


DEFAULT_LOCAL_SETTINGS_TEMPLATE = """
[settings]
web = <url to web site>
downloads = <path to downloads folder>
"""


@_dataclasses.dataclass(kw_only=True, frozen=True)
class Artifact:
    url: str
    download_name: str | None = None

    def __post_init__(self):
        if self.download_name is None:
            guess = guess_download_name_from_url(url=self.url)
            object.__setattr__(self, "download_name", guess)


def guess_download_name_from_url(*, url: str) -> str | None:
    """

    >>> guess_download_name_from_url(url=None)
    >>> guess_download_name_from_url(url="data:...")
    >>> guess_download_name_from_url(url="https://example.com/")
    'example.com.html'
    >>> guess_download_name_from_url(url="https://example.com/file.txt")
    'file.txt'
    >>> guess_download_name_from_url(url="https://example.com/search?q=a%20b")
    'example.com__search__q=a%20b.html'
    >>> guess_download_name_from_url(url="https://example.com/search.json?q=a%20b")
    'example.com__search__q=a%20b.json'

    """

    from urllib.parse import urlparse

    parsed = urlparse(url=url, allow_fragments=True)
    if (parsed.path or "/") == "/":
        ...
    if not parsed.query:
        ...
    return None


def refresh_local_settings(
    *,
    configfile: _pathlib.Path = DEFAULT_LOCAL_SETTINGS_PATH,
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

    from configparser import ConfigParser

    cp = ConfigParser()
    cp.read_string(template, source="<template>")
    cp.read(configfile)
    with configfile.open("w") as f:
        cp.write(f)


def retrieve(*, url: str, download_to: _pathlib.Path) -> _pathlib.Path:
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

    from pathlib import Path
    from shutil import copy2
    from urllib.request import urlcleanup, urlretrieve

    try:
        tmp, msg = urlretrieve(url=url)
        real_downloaded_to = Path(copy2(tmp, download_to))
    finally:
        urlcleanup()
    return real_downloaded_to


def main() -> None:
    from configparser import ConfigParser
    from pathlib import Path
    from urllib.parse import urlparse

    refresh_local_settings()
    cp = ConfigParser()
    cp.read(DEFAULT_LOCAL_SETTINGS_PATH)
    settings = dict(cp["settings"])
    ic(settings)
    web = settings["web"]
    downloads = Path(settings["downloads"])
    downloads.mkdir(exist_ok=True, parents=True)
    webparsed = urlparse(web)
    ic(webparsed)
    webname = webparsed.hostname
    if (webparsed.path or "/") != "/":
        webname += "__" + webparsed.path.replace("/", "__")
    webcopy = downloads / (webname + ".html")
    webcopy = retrieve(url=web, download_to=webcopy)
    ic(webcopy, webcopy.stat())


if __name__ == "__main__":
    import doctest

    failure_count, test_count = doctest.testmod(optionflags=doctest.FAIL_FAST)
    if not failure_count:
        main()
