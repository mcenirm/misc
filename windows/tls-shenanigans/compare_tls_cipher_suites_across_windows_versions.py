from __future__ import annotations

import csv
import datetime
import enum
import pathlib
import shlex
import subprocess
import sys
import time
import typing


MSDOCS_ORG_NAME = "MicrosoftDocs"
MSDOCS_REPO_NAME = "win32"
MSDOCS_GIT_URL = f"https://github.com/{MSDOCS_ORG_NAME}/{MSDOCS_REPO_NAME}.git"
MSDOCS_CLONE = pathlib.Path(MSDOCS_ORG_NAME + "-" + MSDOCS_REPO_NAME)

SECTION_IN_REPO = "desktop-src/SecAuthN"
SECTION_TLS_CIPHER_SUITES_PREFIX = "tls-cipher-suites-in-windows-"
SECTION_TLS_CIPHER_SUITES_EXT = ".md"
SECTION_TLS_CIPHER_SUITES_GLOB = (
    SECTION_TLS_CIPHER_SUITES_PREFIX + "*" + SECTION_TLS_CIPHER_SUITES_EXT
)


def main():
    if MSDOCS_CLONE.exists():
        fetch_time = max(
            [f.stat().st_mtime for f in (MSDOCS_CLONE / ".git").rglob("*")]
        )
        now_time = time.time()
        ago = now_time - fetch_time
        if ago > 86400:
            git(["pull", "--ff-only"], cwd=MSDOCS_CLONE)
        else:
            if ago < 3:
                ago_text = "just now"
            else:
                ago = round(ago)
                if ago < 60:
                    v, t = ago, "s"
                elif ago < 3600:
                    v, t = ago // 60, "m"
                else:
                    v, t = ago // 3600, "h"
                ago_text = f"{v}{t} ago"
            fetch_dt = datetime.datetime.fromtimestamp(fetch_time).astimezone()
            fetch_text = "(" + fetch_dt.isoformat(sep=" ", timespec="minutes") + ")"
            print("++", "fetched", ago_text, fetch_text, file=sys.stderr)
    else:
        git(["clone", "--single-branch", MSDOCS_GIT_URL, MSDOCS_CLONE])

    csvname = "compare-tls-cipher-suite.csv"
    with open(csvname, "w", encoding="utf-8", newline="") as csvf:
        csvw = csv.writer(csvf, dialect=csv.excel)
        csvw.writerow(
            [
                "Windows version",
                HeaderText.CIPHER_SUITE_STRING,
                HeaderText.ALLOWED_BY_SCH_USE_STRONG_CRYPTO,
                HeaderText.TLS_SSL_PROTOCOL_VERSIONS,
                "Comment",
            ]
        )
        for tls_cipher_md in (MSDOCS_CLONE / SECTION_IN_REPO).glob(
            SECTION_TLS_CIPHER_SUITES_GLOB,
            case_sensitive=False,
        ):
            print("++", "reading", tls_cipher_md.name, file=sys.stderr)
            windows_version = (
                tls_cipher_md.stem.removeprefix(SECTION_TLS_CIPHER_SUITES_PREFIX)
                .replace("-version-", "v")
                .replace("-", " ")
            )
            if windows_version == "8 1":
                windows_version = "8.1"
            with tls_cipher_md.open("rt", encoding="utf-8") as f:
                table = first_table_from_markdown(f)
                for r in table.rows:
                    for v in r.tls_ssl_protocol_versions:
                        csvw.writerow(
                            [
                                windows_version,
                                r.cipher_suite_string,
                                r.allowed_by_sch_use_strong_crypto,
                                v,
                                "",
                            ]
                        )
                    if len(r.tls_ssl_protocol_versions) < 1 or r.comment:
                        csvw.writerow(
                            [
                                windows_version,
                                r.cipher_suite_string,
                                r.allowed_by_sch_use_strong_crypto,
                                "",
                                r.comment or "",
                            ]
                        )
    print("++", "wrote", csvname, file=sys.stderr)


def git(command: list[str], *runargs, **runkwargs) -> subprocess.CompletedProcess:
    command = ["git", *map(str, command)]
    runkwargs = dict(check=True) | runkwargs
    print("+", *map(shlex.quote, map(str, command)), file=sys.stderr)
    return subprocess.run(command, *runargs, **runkwargs)


class TLSProtocolVersion(enum.StrEnum):
    TLS_1_3 = "TLS 1.3"
    TLS_1_2 = "TLS 1.2"
    TLS_1_1 = "TLS 1.1"
    TLS_1_0 = "TLS 1.0"
    SSL_3_0 = "SSL 3.0"
    SSL_2_0 = "SSL 2.0"


class TLSCipherSuite:
    def __init__(
        self,
        cipher_suite_string: str,
        allowed_by_sch_use_strong_crypto: bool,
        tls_ssl_protocol_versions: set[TLSProtocolVersion],
        comment: str = None,
    ):
        cipher_suite_string = str(cipher_suite_string)
        if comment is None and " " in cipher_suite_string:
            cipher_suite_string, comment = cipher_suite_string.split(
                " ",
                maxsplit=1,
            )
            comment = comment.strip()
        self.cipher_suite_string = cipher_suite_string
        self.comment = comment

        if isinstance(allowed_by_sch_use_strong_crypto, str):
            allowed_by_sch_use_strong_crypto = str(
                allowed_by_sch_use_strong_crypto
            ).lower() in {"y", "yes", "t", "true"}
        self.allowed_by_sch_use_strong_crypto = bool(allowed_by_sch_use_strong_crypto)

        if isinstance(tls_ssl_protocol_versions, TLSProtocolVersion):
            tls_ssl_protocol_versions = [tls_ssl_protocol_versions]
        elif isinstance(tls_ssl_protocol_versions, str):
            tls_ssl_protocol_versions = [
                s.strip() for s in tls_ssl_protocol_versions.upper().split(",")
            ]
        self.tls_ssl_protocol_versions = frozenset(
            map(TLSProtocolVersion, tls_ssl_protocol_versions)
        )

    def __repr__(self):
        args = [
            repr(self.cipher_suite_string),
            repr(self.allowed_by_sch_use_strong_crypto),
            "".join(
                [
                    "{",
                    ",".join(
                        [
                            repr(v.value)
                            for v in sorted(
                                self.tls_ssl_protocol_versions, reverse=True
                            )
                        ]
                    ),
                    "}",
                ]
            ),
        ]
        if self.comment is not None:
            args.append(self.comment)
        return "".join(
            [
                self.__class__.__name__,
                "(",
                ",".join(args),
                ")",
            ]
        )


class HeaderText(enum.StrEnum):
    CIPHER_SUITE_STRING = "Cipher suite string"
    ALLOWED_BY_SCH_USE_STRONG_CRYPTO = "Allowed by SCH_USE_STRONG_CRYPTO"
    TLS_SSL_PROTOCOL_VERSIONS = "TLS/SSL Protocol versions"

    @classmethod
    def _missing_(cls, value: str):
        for member in cls:
            if member.value.lower() == value.lower():
                return member
        return super()._missing_(value)


class TLSCipherSuitesTable:
    def __init__(self, header: list[str]):
        self.header = list(header)
        self.rows: list[TLSCipherSuite] = []
        self._indices = {
            HeaderText.CIPHER_SUITE_STRING: -1,
            HeaderText.ALLOWED_BY_SCH_USE_STRONG_CRYPTO: -1,
            HeaderText.TLS_SSL_PROTOCOL_VERSIONS: -1,
        }
        errors = []
        for idx, text in enumerate(self.header):
            head = HeaderText(text)
            if head in self._indices:
                if self._indices[head] < 0:
                    self._indices[head] = idx
                else:
                    errors.append(
                        (
                            "duplicate header",
                            text,
                            f"previous index: {self._indices[head]}",
                            f"other index: {idx}",
                        )
                    )
            else:
                errors.append(("unexpected header value", text))
        for text, idx in self._indices.items():
            if idx < 0:
                errors.append(("missing header", text))
        if errors:
            raise ValueError(*errors)

    def append(self, row: list[str]) -> None:
        self.rows.append(
            TLSCipherSuite(
                cipher_suite_string=row[self._indices[HeaderText.CIPHER_SUITE_STRING]],
                allowed_by_sch_use_strong_crypto=row[
                    self._indices[HeaderText.ALLOWED_BY_SCH_USE_STRONG_CRYPTO]
                ],
                tls_ssl_protocol_versions=row[
                    self._indices[HeaderText.TLS_SSL_PROTOCOL_VERSIONS]
                ],
            )
        )


def first_table_from_markdown(f: typing.TextIO) -> TLSCipherSuitesTable:
    table = None
    for line in f:
        if line.startswith("|"):
            cells = list(
                map(demarkdown_text, map(str.strip, line.strip().strip("|").split("|")))
            )
            if table is None:
                table = TLSCipherSuitesTable(cells)
            else:
                is_header_rule = all([all([c == "-" for c in s]) for s in cells])
                if not is_header_rule:
                    table.append(cells)
        elif table is not None:
            break
    return table


def demarkdown_text(text: str) -> str:
    return text.replace("<br>", " ").replace("<br/>", " ").replace("\\_", "_")


if __name__ == "__main__":
    main()
