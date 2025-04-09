from __future__ import annotations

import dataclasses
import enum
import typing

if typing.TYPE_CHECKING:
    from .check import Check


class ResultState(enum.StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TODO = "TODO"


@dataclasses.dataclass
class CheckResult:
    chk: Check
    state: ResultState
    reason: str | None = None
    expected: typing.Any | None = None
    actual: typing.Any | None = None


@dataclasses.dataclass
class CheckReport:
    results: dict[str, CheckResult] = dataclasses.field(default_factory=dict)

    def add(self, result: CheckResult) -> None:
        self.results[result.chk.s.nasa_ascs_id] = result
