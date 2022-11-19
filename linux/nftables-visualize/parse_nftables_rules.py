from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, TextIO


@dataclass(frozen=True, kw_only=True)
class Rules:
    tables: dict[str, Table] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class Table:
    category: str
    name: str
    chains: dict[str, Chain] = field(default_factory=dict)

    def add_chain(self, ch: Chain) -> None:
        self.chains[ch.name] = ch


@dataclass(frozen=True, kw_only=True)
class Chain:
    name: str


@dataclass(frozen=True, kw_only=True)
class _BlocksFromTextIO:
    source: TextIO
    # def __iter__(self)->Iterator[]


@dataclass(frozen=True, kw_only=True)
class _Block:
    noun: str
    modifiers: list[str]
    name: str
    suite: list[str]


@dataclass(frozen=True, kw_only=True)
class _Statement:
    words: list[str]


def parse_nftables_rules(rules: TextIO) -> Rules:
    r = Rules()
    for block in _BlocksFromTextIO(source=rules):
        ...
    return r
