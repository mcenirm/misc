from __future__ import annotations

import dataclasses
import json
import math
import pathlib
import re
import shlex
import sqlite3
import sys
import typing

# Bad attempt to clean up duplicates in the "worse" bucket,
# if there are objects with the same keys and sizes in a "better" bucket.
#
# TODO: Look at using S3 Batch instead? Generate manifest.json?


@dataclasses.dataclass(frozen=True)
class S3ListingEntry:
    mtime: str
    sizebytes: int
    key: str


class S3CompareListings:
    def __init__(
        self, better_s3uri: str, worse_s3uri: str, ignore_directories: bool = True
    ):
        self.better_s3uri = str(better_s3uri)
        self.worse_s3uri = str(worse_s3uri)
        self.ignore_directories = ignore_directories
        self.db = sqlite3.connect(":memory:")
        self.db.execute(
            "create table compare(key text unique, bettersize integer, worsesize integer, bettermtime text, worsemtime text)"
        )

    def update_entries(
        self, better_or_worse: str, entries: typing.Iterable[S3ListingEntry]
    ):
        size = f"{better_or_worse}size"
        mtime = f"{better_or_worse}mtime"
        sql = f"insert into compare(key, {size}, {mtime}) values (?,?,?) on conflict(key) do update set {size}=excluded.{size}, {mtime}=excluded.{mtime}"
        self.db.cursor().executemany(
            sql,
            (
                (e.key, e.sizebytes, e.mtime)
                for e in entries
                if not (self.ignore_directories and e.key.endswith("/"))
            ),
        ).close()

    def __len__(self) -> int:
        cur = self.db.cursor()
        try:
            return cur.execute("select count(*) from compare").fetchone()[0]
        finally:
            cur.close()

    def _entries(self, better_or_worse: str) -> list[S3ListingEntry]:
        cur = self.db.cursor()
        size = f"{better_or_worse}size"
        mtime = f"{better_or_worse}mtime"
        try:
            return [
                S3ListingEntry(key=row[0], sizebytes=int(row[1]), mtime=row[2])
                for row in cur.execute(
                    f"select key, {size}, {mtime} from compare where {size} is not null"
                ).fetchall()
            ]
        finally:
            cur.close()

    def better_entries(self) -> list[S3ListingEntry]:
        return self._entries("better")

    def worse_entries(self) -> list[S3ListingEntry]:
        return self._entries("worse")

    def _size_entries(self, same: bool) -> list[tuple[S3ListingEntry, S3ListingEntry]]:
        sql = f"select key, bettersize, bettermtime, worsesize, worsemtime from compare where bettersize is not null and worsesize is not null and bettersize {'=' if same else '!='} worsesize"
        cur = self.db.cursor()
        try:
            return [
                (
                    S3ListingEntry(key=row[0], sizebytes=int(row[1]), mtime=row[2]),
                    S3ListingEntry(key=row[0], sizebytes=int(row[3]), mtime=row[4]),
                )
                for row in cur.execute(sql).fetchall()
            ]
        finally:
            cur.close()

    def same_size_entries(self) -> list[tuple[S3ListingEntry, S3ListingEntry]]:
        return self._size_entries(same=True)

    def not_same_size_entries(self) -> list[tuple[S3ListingEntry, S3ListingEntry]]:
        return self._size_entries(same=False)


class S3SimpleListing:
    def __init__(self, s3uri: str):
        self.s3uri = str(s3uri)
        self.db = sqlite3.connect(":memory:")
        self.db.execute("create table listing(mtime text, sizebytes integer, key text)")

    def load(self, path: pathlib.Path):
        f = pathlib.Path(path).open("rt", encoding="UTF-8")
        cur = self.db.cursor()
        try:
            with f:
                cur.executemany(
                    "insert into listing(mtime, sizebytes, key) values (?,?,?)",
                    listing_lines(f),
                )
        finally:
            cur.close()

    def __len__(self) -> int:
        cur = self.db.cursor()
        try:
            cur.execute("select count(*) from listing")
            return cur.fetchone()[0]
        finally:
            cur.close()


def listing_lines(
    f: typing.TextIO,
) -> typing.Generator[tuple[str, int, str], None, None]:
    pattern = re.compile(
        r"^(?P<mtime>\d+-\d+-\d+\s+\d+:\d+:\d+)\s+(?P<sizebytes>\d+)\s+(?P<key>.+)"
    )
    for line in f:
        matched = pattern.match(line)
        if matched:
            groups = matched.groups()
            yield (str(groups[0]), int(groups[1]), str(groups[2]))
        else:
            print("!!", line, file=sys.stderr)
            sys.exit(1)


def read_entries(
    f: typing.TextIO,
) -> typing.Generator[S3ListingEntry, None, None]:
    pattern = re.compile(
        r"^(?P<mtime>\d+-\d+-\d+\s+\d+:\d+:\d+)\s+(?P<sizebytes>\d+)\s+(?P<key>.+)"
    )
    for lineno, line in enumerate(f, 1):
        matched = pattern.match(line)
        if matched:
            yield S3ListingEntry(**(matched.groupdict()))
        else:
            print("!!", lineno, line, file=sys.stderr)
            sys.exit(1)


def main1():
    betterfile, worsefile = [pathlib.Path(a) for a in sys.argv[1:3]]
    betters3uri, worses3uri = [
        f"s3://{f.name.removeprefix('example.').removesuffix('.lst')}/"
        for f in (betterfile, worsefile)
    ]
    betterlist, worselist = [S3SimpleListing(u) for u in (betters3uri, worses3uri)]
    for l, f in [(betterlist, betterfile), (worselist, worsefile)]:
        l.load(f)
        print(f"++  {len(l):>7}  {l.s3uri}")


def main2():
    betterpath, worsepath = [pathlib.Path(a) for a in sys.argv[1:3]]
    betterbucket, worsebucket = [
        p.name.removeprefix("example.").removesuffix(".lst")
        for p in (betterpath, worsepath)
    ]
    betters3uri, worses3uri = [f"s3://{b}/" for b in (betterbucket, worsebucket)]
    compare = S3CompareListings(betters3uri, worses3uri)
    for better_or_worse, p in [
        ("better", betterpath),
        ("worse", worsepath),
    ]:
        f = pathlib.Path(p).open("rt", encoding="UTF-8")
        with f:
            compare.update_entries(better_or_worse, read_entries(f))
        s3uri = getattr(compare, better_or_worse + "_s3uri", "")
        print(f"##  {better_or_worse:<8}  {len(compare):>7}  {s3uri}", file=sys.stderr)

    same_sizes = compare.same_size_entries()
    print(f"##  samesize  {len(same_sizes):>7}", file=sys.stderr)
    not_same_sizes = compare.not_same_size_entries()
    print(f"##  diffsize  {len(not_same_sizes):>7}", file=sys.stderr)
    delete_worse_keys = []
    with open("example.remove-worse.txt", "wt") as chunkout:
        command_prefix = "aws s3 rm " + shlex.quote(compare.worse_s3uri)
        for better, worse in same_sizes:
            print(command_prefix + shlex.quote(worse.key), file=chunkout)
            delete_worse_keys.append(worse.key)
    delete_worse_keys.sort()
    chunksize = 1000
    chunkcount = math.ceil(len(delete_worse_keys) / chunksize)
    chunknumwidth = math.ceil(math.log10(chunkcount))
    chunkoutnamefmt = f"example.delete-worse.{{chunkno:0{chunknumwidth}}}.json"
    chunknum = 0
    with open("example.delete-worse.sh.txt", "wt") as shout:
        for i in range(0, len(delete_worse_keys), chunksize):
            chunknum += 1
            chunkoutname = chunkoutnamefmt.format(chunkno=chunknum)
            print(
                f"aws s3api delete-objects --bucket {shlex.quote(worsebucket)} --delete file://{shlex.quote(chunkoutname)}",
                file=shout,
            )
            with open(chunkoutname, "wt") as chunkout:
                json.dump(
                    dict(
                        Objects=[
                            dict(Key=k)
                            for k in delete_worse_keys[
                                i : min(len(delete_worse_keys), i + chunksize)
                            ]
                        ],
                        Quiet=True,
                    ),
                    chunkout,
                    indent=" ",
                )


def main():
    main2()


if __name__ == "__main__":
    main()
