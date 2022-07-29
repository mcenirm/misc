from __future__ import annotations

import datetime
import pathlib
import re as _re
from dataclasses import dataclass as _dataclass


@_dataclass(kw_only=True, frozen=True)
class Settings:
    feed: FeedSettings
    not_too_soon: datetime.timedelta


@_dataclass(kw_only=True, frozen=True)
class FeedSettings:
    url: str
    file: str


@_dataclass(kw_only=True, frozen=True)
class FeedStatus:
    pub_date: datetime.datetime | None
    last_build_date: datetime.datetime | None


def main():
    settings = load_settings()
    if should_we_grab_the_feed(settings.feed, settings.not_too_soon):
        print(grab(settings.feed))


def grab(feed: FeedSettings, previous_prefix: str = "previous.") -> pathlib.Path:
    from shutil import copy2
    from urllib.request import urlretrieve, urlcleanup

    previous = pathlib.Path(feed.file)
    if previous.is_symlink():
        previous.rename(previous.with_stem(previous_prefix + previous.stem))
    elif previous.exists():
        raise FileExistsError(
            "expected existing feed file to be a symlink",
            feed.file,
        )
    try:
        tmpf, msg = urlretrieve(url=feed.url)
        dest = copy2(tmpf, feed.file)
    finally:
        # TODO maybe add a setting to skip cleanup and show tmpf,msg for troubleshooting?
        urlcleanup()
    target = replace_with_symlink_based_on_feed_date(pathlib.Path(dest))
    headers_path = pathlib.Path(str(target) + ".headers.txt")
    with headers_path.open("w") as f:
        f.write(msg.as_string())
    return target


def load_settings(name="grabby"):
    from configparser import ConfigParser

    cp = ConfigParser()
    ini = name + ".ini"
    readinis = cp.read(name + ".ini")
    if ini not in readinis:
        raise FileNotFoundError(ini)
    s = cp["settings"]
    settings = Settings(
        feed=FeedSettings(
            url=s["feed_url"],
            file=s["feed_file"],
        ),
        not_too_soon=parse_timedelta(s["not_too_soon"]),
    )
    return settings


_PARSE_TIMEDELTA_PATTERN = _re.compile(r"^\s*(\d+)([hms])")


def parse_timedelta(s: str) -> datetime.timedelta:
    from collections import defaultdict

    x = defaultdict(float)
    while s and (m := _PARSE_TIMEDELTA_PATTERN.match(s)):
        value, unit = m.groups()
        x[unit] += float(value)
        s = s[m.span()[1] :]
    td = datetime.timedelta(seconds=x["s"], minutes=x["m"], hours=x["h"])
    return td


def should_we_grab_the_feed(feed: FeedSettings, not_too_soon: datetime.timedelta):
    feed_path = pathlib.Path(feed.file)
    if not feed_path.exists():
        return True
    if feed_path.is_symlink():
        target = feed_path.readlink()
    elif feed_path.is_file():
        target = replace_with_symlink_based_on_feed_date(feed_path)
    mtime = mtime_as_datetime(target)
    age = datetime.datetime.utcnow() - mtime
    return age > not_too_soon


def replace_with_symlink_based_on_feed_date(
    feed_path: pathlib.Path,
) -> pathlib.Path:
    from os import utime

    mtime = mtime_as_datetime(feed_path)
    status = guess_feed_status(feed_path)
    feed_datatime = status.pub_date or status.last_build_date or mtime
    if mtime != feed_datatime:
        utime(feed_path, times=(feed_datatime.timestamp(), feed_datatime.timestamp()))
    target = replace_with_symlink_based_on_datetime(feed_path, feed_datatime)
    return target


def replace_with_symlink_based_on_datetime(
    p: pathlib.Path,
    d: datetime.datetime,
) -> pathlib.Path:
    if p.is_symlink():
        return p.readlink()
    target = path_with_datetime(p, d)
    p.rename(target=target)
    p.symlink_to(target=target.name)
    return target


def path_with_datetime(p: pathlib.Path, d: datetime.datetime) -> pathlib.Path:
    return pathlib.Path(
        ".".join(
            [
                str(p),
                str(int(d.timestamp())),
                d.strftime("%Y-%m-%d"),
            ]
        )
    )


def mtime_as_datetime(p: pathlib.Path) -> datetime.datetime:
    return datetime.datetime.utcfromtimestamp(p.stat().st_mtime)


def guess_feed_status(feed_file: pathlib.Path) -> FeedStatus:
    import xml.etree.ElementTree as ET
    from email.utils import parsedate_to_datetime

    tree = ET.parse(feed_file)
    rss = tree.getroot()
    channel = rss.find("channel")
    pub_date_str = channel.findtext("pubDate")
    last_build_date_str = channel.findtext("lastBuildDate")
    pub_date = parsedate_to_datetime(pub_date_str)
    last_build_date = parsedate_to_datetime(last_build_date_str)
    fs = FeedStatus(pub_date=pub_date, last_build_date=last_build_date)
    return fs


if __name__ == "__main__":
    main()
