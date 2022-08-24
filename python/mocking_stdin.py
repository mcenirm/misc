from __future__ import annotations

from io import StringIO
from pathlib import Path
from sys import argv
from typing import Generator, TextIO
from unittest import TestCase
from unittest import main as utmain
from unittest.mock import patch

ALL = ["lenlines", "main"]


PROG = Path(__file__).stem


def lenlines(stream: TextIO) -> Generator[int, None, None]:
    for line in stream:
        yield len(line)


def main():
    from sys import stdin

    for i, x in enumerate(lenlines(stdin)):
        print(i, x)


class TestMockingStdin(TestCase):
    def test_direct(self):
        stream = StringIO("one\ntwo\n\nfour\n")
        expected = [4, 4, 1, 5]
        actual = list(lenlines(stream))
        self.assertListEqual(actual, expected)

    def test_mocking_stdin(self):
        stream = StringIO("one\ntwo\n\nfour\n")
        expected = [" ".join(map(str, (i, x))) for i, x in enumerate([4, 4, 1, 5])]
        output = StringIO()
        with patch("sys.stdin", stream), patch("sys.stdout", output):
            main()
        actual = output.getvalue().splitlines()
        self.assertListEqual(actual, expected)


if __name__ == "__main__":
    args = argv[1:]
    if args and args[0] in ("-u", "-t", "-unittest", "--unittest"):
        utmain(argv=[argv[0], *args[1:]])
    elif args and args[0] in ("-h", "-help", "--help"):
        print(f"Usage: {PROG} --help | --unittest")
    else:
        main()
