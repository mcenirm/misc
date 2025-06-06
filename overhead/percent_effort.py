from __future__ import annotations

import ast
import math
import re
import string
import sys
from collections.abc import KeysView, Mapping, MutableMapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import total_ordering
from logging import warning
from typing import Optional, TextIO, Type
from urllib.parse import urlparse

from icecream import ic  # type: ignore
from rich import inspect as rinspect
from rich import print as rprint
from rich.table import Column, Table


def _build_abbreviations(fmt: str, incr_days: int) -> set[str]:
    abbreviations = set()
    delta = timedelta(days=incr_days)
    day = GOOD_MONDAY
    while (abbr := day.strftime(fmt).upper()) not in abbreviations:
        abbreviations.add(abbr)
        day += delta
    return abbreviations


# The first day of 2001 was a Monday, but this is arbitrary.
GOOD_MONDAY = datetime.strptime("2001-01-01", "%Y-%m-%d").date()

WEEKDAY_ABBREVIATIONS = _build_abbreviations("%a", 1)
MONTH_ABBREVIATIONS = _build_abbreviations("%b", 31)

MAX_HOURS = 80
SPREADSHEET_URL_PREFIX = "https://docs.google.com/spreadsheets/d/"
RE_NUMBER_OF_HOURS = re.compile(
    r"\b(?P<number_of_hours>\d+(?:[.,]\d+)?)\s*h(?:ou)?rs?\b",
    re.IGNORECASE,
)

AUX_TABLE_DATE_FORMAT = "%A, %b %d, %Y"  # Tuesday, Apr 05, 2022
AUX_KEY_PREFIX = "z-"


class DayParser:
    def __init__(self, __format: str) -> None:
        self._format_handles_year = self._does_day_format_handle_year(__format)
        if self.format_handles_year:
            self._format = __format
        else:
            self._format = f"%Y {__format}"

    @property
    def format(self):
        return self._format

    @property
    def format_handles_year(self):
        return self._format_handles_year

    def parse_day(self, day: str) -> Optional[date]:
        if self.format_handles_year:
            return self._parse_day(day)
        else:
            return self._parse_day_by_guessing_year(day)

    def _parse_day(self, day: str) -> Optional[date]:
        try:
            return self._strpdate(day, self.format)
        except ValueError:
            return None

    def _parse_day_by_guessing_year(self, day: str) -> Optional[date]:
        today = date.today()
        guesses = []
        for dy in [-1, 0, +1]:
            year_and_day = f"{today.year + dy} {day}"
            guess = self._parse_day(year_and_day)
            if guess:
                guesses.append(guess)
        if guesses:
            closest_day = sorted(
                guesses,
                key=lambda g: math.fabs(
                    today.toordinal() - g.toordinal(),
                ),
            )[0]
            return closest_day
        else:
            return None

    @staticmethod
    def _strpdate(__date_string: str, __format: str) -> date:
        return datetime.strptime(__date_string, __format).date()

    @staticmethod
    def _does_day_format_handle_year(__format: str) -> bool:
        import warnings

        today = date.today()
        today_as_string = today.strftime(__format)

        # Suppress errors and warnings, since the goal of this test is simply
        # to determine if parse_day() should try year-guessing.
        #
        # If the format is truly unusable, then subsequent calls to parse_day()
        # will expose the problem.
        #
        # > Changed in version 3.13: If format specifies a day of month
        # > without a year a DeprecationWarning is now emitted. This is to
        # > avoid a quadrennial leap year bug in code seeking to parse only a
        # > month and day as the default year used in absence of one in the
        # > format is not a leap year. Such format values may raise an error
        # > as of Python 3.15.
        # >
        # > - <https://docs.python.org/3.13/library/datetime.html#datetime.datetime.strptime>

        reparsed_today = None
        with warnings.catch_warnings(action="error"):
            try:
                reparsed_today = DayParser._strpdate(today_as_string, __format)
            except DeprecationWarning:
                pass
            except ValueError:
                pass

        return today == reparsed_today


DAY_PARSER = DayParser("%a %b %d")
DAY_ENTRY_PARTS_SEPARATOR = " - "

DistributionAccountName = str
DistributionConstraintSpecification = str
EffortHours = float
EffortPercent = float
EffortPoints = float
EntrySpecification = str


@total_ordering
@dataclass(frozen=True)
class EntryKey:
    s: str

    @classmethod
    def from_str(cls, s: str) -> EntryKey:
        if s:
            return cls(s.strip())

    def __lt__(self, other):
        return self.s < str(other)

    def __eq__(self, other):
        return self.s == str(other)

    def __str__(self) -> str:
        return self.s

    def is_auxiliary(self):
        return self.s.startswith(AUX_KEY_PREFIX)

    def title(self):
        return self.s.removeprefix(AUX_KEY_PREFIX).title()


@dataclass(frozen=True)
class DistributionConstraint:
    distribution_account_name: DistributionAccountName

    @classmethod
    def fromspec(
        cls: Type["DistributionConstraint"],
        spec: DistributionConstraintSpecification,
        /,
    ) -> Optional["DistributionConstraint"]:
        raise NotImplementedError()


@dataclass(frozen=True)
class PercentEffortDistributionConstraint(DistributionConstraint):
    min_percent: EffortPercent
    max_percent: EffortPercent


@dataclass(frozen=True)
class HourDistributionConstraint(DistributionConstraint):
    min_hours: EffortHours
    max_hours: EffortHours

    @classmethod
    def fromspec(
        cls: Type["HourDistributionConstraint"],
        spec: DistributionConstraintSpecification,
        /,
    ) -> Optional["HourDistributionConstraint"]:
        before_and_hours_and_after = RE_NUMBER_OF_HOURS.split(spec, maxsplit=1)
        if len(before_and_hours_and_after) != 3:
            return None
        before, number_of_hours, after = before_and_hours_and_after
        # TODO min vs max?
        after = after.lstrip(string.punctuation).strip()
        return cls(
            DistributionAccountName(after),
            EffortHours(0),
            EffortHours(ast.literal_eval(number_of_hours)),
        )


@dataclass(frozen=True)
class RemainderDistributionConstraint(DistributionConstraint):
    @classmethod
    def fromspec(
        cls: Type["RemainderDistributionConstraint"],
        spec: DistributionConstraintSpecification,
        /,
    ) -> Optional["RemainderDistributionConstraint"]:
        words = spec.split()
        if not words:
            return None
        if words[0] in ("rest", "remainder", "else"):
            spec = spec.removeprefix(words[0]).strip()
            words.pop(0)
        if words:
            return cls(DistributionAccountName(spec))
        else:
            return None


@dataclass
class Score:
    points: EffortPoints = EffortPoints(0)
    hours: EffortHours = EffortHours(0)
    auxiliary_points: EffortPoints = EffortPoints(0)
    auxiliary_hours: EffortHours = EffortHours(0)
    percent_effort: EffortPercent = EffortPercent(0)

    def __iadd__(self, other: "Score") -> "Score":
        self.points += other.points
        self.hours += other.hours
        self.auxiliary_points += other.auxiliary_points
        self.auxiliary_hours += other.auxiliary_hours
        return self

    def __repr__(self) -> str:
        ps = []
        for attrname in [
            "points",
            "hours",
            "auxiliary_points",
            "auxiliary_hours",
            "percent_effort",
        ]:
            value = getattr(self, attrname, None)
            if value:
                ps.append(f"{attrname}={value}")
        return f"{self.__class__.__name__}({', '.join(ps)})"


class Summary(dict[EntryKey, Score]):
    def __getitem__(self, __k: EntryKey) -> Score:
        try:
            return super().__getitem__(__k)
        except KeyError:
            sc = Score()
            self[__k] = sc
            return sc


@dataclass(frozen=True)
class Entry:
    key: EntryKey

    @classmethod
    def fromspec(
        cls: Type["Entry"],
        spec: EntrySpecification,
        /,
    ) -> Optional["Entry"]:
        raise NotImplementedError()

    def as_score(self) -> Score:
        return Score()

    def is_auxiliary(self):
        return self.key.is_auxiliary()


@dataclass(frozen=True)
class PointsEntry(Entry):
    points: EffortPoints

    @classmethod
    def fromspec(
        cls: Type["PointsEntry"],
        spec: EntrySpecification,
        /,
    ) -> Optional["PointsEntry"]:
        try:
            key_and_points = spec.split(maxsplit=1)
            key = EntryKey(key_and_points[0].strip().lower())
            points = EffortPoints(ast.literal_eval(key_and_points[1]))
            return cls(key, points)
        except ValueError:
            return None

    def as_score(self) -> Score:
        s = Score()
        if self.is_auxiliary():
            s.auxiliary_points = self.points
        else:
            s.points = self.points
        return s


@dataclass(frozen=True)
class HoursEntry(Entry):
    hours: EffortHours

    @classmethod
    def fromspec(
        cls: Type["HoursEntry"],
        spec: EntrySpecification,
        /,
    ) -> Optional["HoursEntry"]:
        before_and_hours_and_after = RE_NUMBER_OF_HOURS.split(spec, maxsplit=1)
        if len(before_and_hours_and_after) != 3:
            return None
        key = EntryKey(before_and_hours_and_after[0].strip().lower())
        hours = ast.literal_eval(before_and_hours_and_after[1])
        return cls(key, hours)

    def as_score(self) -> Score:
        s = Score()
        if self.is_auxiliary():
            s.auxiliary_hours = self.hours
        else:
            s.hours = self.hours
        return s


class DistributionConstraintByAccountNameDict(
    dict[DistributionAccountName, DistributionConstraint]
):
    pass


class DistributionConstraintsByEntryKeyDict(
    dict[EntryKey, DistributionConstraintByAccountNameDict]
):
    pass


@dataclass
class Book:
    spreadsheet_url: Optional[str] = None
    distribution_constraints_by_entry_key: DistributionConstraintsByEntryKeyDict = (
        field(default_factory=DistributionConstraintsByEntryKeyDict)
    )
    entries_by_day_and_key: MutableMapping[tuple[date, EntryKey], Entry] = field(
        default_factory=dict
    )
    summary: Summary = field(default_factory=Summary)

    def constrain(
        self,
        entry_key: EntryKey,
        constraints: set[DistributionConstraint],
        /,
        context_description_in_case_of_error: Optional[str] = None,
    ) -> None:
        if entry_key in self.distribution_constraints_by_entry_key:
            if context_description_in_case_of_error:
                context_description_in_case_of_error = (
                    " " + context_description_in_case_of_error.lstrip()
                )
            raise ValueError(
                f"distribution constraint key {entry_key!r} reused{context_description_in_case_of_error}"
            )
        else:
            sorted_constraints = sorted(
                constraints, key=lambda _: _.distribution_account_name
            )
            constraints_by_account_name = DistributionConstraintByAccountNameDict()
            for constraint in sorted_constraints:
                constraints_by_account_name[
                    constraint.distribution_account_name
                ] = constraint
            self.distribution_constraints_by_entry_key[
                entry_key
            ] = constraints_by_account_name

    def add_day_entries(self, day: date, entries: list[Entry]) -> None:
        for entry in entries:
            self.add_entry(day, entry)

    def add_entry(self, day: date, entry: Entry) -> None:
        t = (day, entry.key)
        if t in self.entries_by_day_and_key:
            raise ValueError(f"already saw day-key entry: {t}")
        self.entries_by_day_and_key[t] = entry

    def keys(self) -> KeysView[EntryKey]:
        return dict.fromkeys(
            sorted([_[1] for _ in self.entries_by_day_and_key.keys()])
        ).keys()

    def entries_for_key(self, key) -> Mapping[date, Entry]:
        r = {
            day_and_key[0]: entry
            for day_and_key, entry in self.entries_by_day_and_key.items()
            if day_and_key[1] == key
        }
        return r

    def distribute(self) -> bool:
        # TODO while book.distribute(): print book?
        for key in self.keys():
            constraints = self.distribution_constraints_by_entry_key.get(
                key, DistributionConstraintByAccountNameDict()
            )
            count = len(constraints)
            if count:
                days_to_remove = set()
                for day, entry in self.entries_for_key(key).items():
                    days_to_remove.add(day)
                    for constraint in constraints.values():
                        # TODO distribute current entry to constrained entries?
                        ...
                for day in days_to_remove:
                    del self.entries_by_day_and_key[(day, key)]
                return True
        return False

    def summarize(self) -> Summary:
        self.summary.clear()
        for key in self.keys():
            for _, entry in self.entries_for_key(key).items():
                self.summary[key] += entry.as_score()
        return self.summary

    def auxiliary_table(self) -> Table:
        all_dates = sorted({d for d, _ in self.entries_by_day_and_key.keys()})
        first_date = all_dates[0]
        last_date = all_dates[-1]
        num_days = (last_date - first_date + timedelta(days=1)).days
        all_dates = [first_date + timedelta(days=i) for i in range(num_days)]

        all_auxillary_keys = sorted(
            {k for (_, k), e in self.entries_by_day_and_key.items() if e.is_auxiliary()}
        )

        stuck_columns = ["Earning Code", "Shift", "Total Hours", "Total Units"]
        headers = stuck_columns + [_.strftime(AUX_TABLE_DATE_FORMAT) for _ in all_dates]
        t = Table(*headers)

        for auxillary_key in all_auxillary_keys:
            x = []
            total_hours = 0
            for d in all_dates:
                he = self.entries_by_day_and_key.get((d, auxillary_key), None)
                if he and isinstance(he, HoursEntry):
                    total_hours += he.hours
                    v = str(he.hours)
                else:
                    v = ""
                x.append(v)
            t.add_row(
                auxillary_key.title(),
                "",
                str(total_hours) if total_hours else "",
                "",
                *x,
            )

        return t

    @staticmethod
    def totals(s: Summary, /) -> Score:
        t = Score()
        for key, score in s.items():
            t += score
        return t


def parse_as_spreadsheet_url(line: str, /) -> Optional[str]:
    if line.startswith(SPREADSHEET_URL_PREFIX):
        result = urlparse(line)
        return result.geturl()
    else:
        return None


def parse_as_entry_key_and_distribution_constraint_set(
    line: str,
    /,
) -> Optional[tuple[EntryKey, set[DistributionConstraint]]]:
    key_and_specs = line.split(":", maxsplit=1)
    if len(key_and_specs) == 1:
        return None
    else:
        key, specs = key_and_specs
        key = key.strip().lower()
        spec_list = [str(_).strip() for _ in specs.split(";")]
        constraints = set()
        for spec in spec_list:
            for cls in [HourDistributionConstraint, RemainderDistributionConstraint]:
                fromspec = getattr(cls, "fromspec")
                constraint = fromspec(spec)
                if constraint:
                    constraints.add(constraint)
                    break
        return EntryKey.from_str(key), constraints


def parse_as_day_and_entry_list(
    line: str,
    /,
) -> Optional[tuple[date, list[Entry]]]:
    day_and_entry_list = list(line.split(DAY_ENTRY_PARTS_SEPARATOR))
    if len(day_and_entry_list) < 2:
        return None
    day = DAY_PARSER.parse_day(day_and_entry_list[0])
    if not day:
        return None
    entry_list = []
    for entry_spec in day_and_entry_list[1:]:
        for cls in [HoursEntry, PointsEntry]:
            fromspec = getattr(cls, "fromspec")
            entry = fromspec(entry_spec)
            if entry:
                entry_list.append(entry)
                break
    if entry_list:
        return day, entry_list
    else:
        return None


def effort_table_row(
    reported_hours,
    effortable_hours,
    to_be_allocated_hours,
    adjusted_percent_effort,
    percent_effort,
    key,
    score,
) -> list[str]:
    return [
        f"{reported_hours:5.1f}" if reported_hours else "---",
        f"{effortable_hours:5.1f}" if effortable_hours else "---",
        f"{to_be_allocated_hours:5.1f}" if to_be_allocated_hours else "---",
        f"{adjusted_percent_effort:7.1%}" if adjusted_percent_effort else "---",
        f"{percent_effort:7.1%}" if percent_effort else "---",
        str(key) if key else "---",
        str(score) if score else "---",
    ]


def load(infile: TextIO, book: Book) -> None:
    for line_num, line in enumerate([""] + [str(_).strip() for _ in infile]):
        if not line or line.upper() in WEEKDAY_ABBREVIATIONS:
            continue

        if url := parse_as_spreadsheet_url(line):
            book.spreadsheet_url = url
        elif key_and_set := parse_as_entry_key_and_distribution_constraint_set(line):
            key, dcs = key_and_set
            book.constrain(key, dcs, f"at line {line_num}")
        elif day_and_entries := parse_as_day_and_entry_list(line):
            day, entries = day_and_entries
            book.add_day_entries(day, entries)
        else:
            warning("unrecognized line: %r", line)


def run(stdin, /) -> None:
    book = Book()
    load(stdin, book)
    constraints_by_key = book.distribution_constraints_by_entry_key
    book_summary = book.summarize()
    book_totals = Book.totals(book_summary)
    ic(book_totals)

    total_hours = book_totals.hours + book_totals.auxiliary_hours
    ic(total_hours)
    total_points = book_totals.points + book_totals.auxiliary_points
    ic(total_points)
    effortable_hours = MAX_HOURS - total_hours
    if effortable_hours < 0:
        warning(
            f"Total hours exceeds max hours ({total_hours} > {MAX_HOURS}). Points will be ignored."
        )
        effortable_hours = 0
        hours_per_point = 0
    elif total_points > 0:
        hours_per_point = effortable_hours / total_points
    ic(effortable_hours)
    ic(hours_per_point)

    total_percent_effort = 0
    total_adjusted_percent_effort = 0
    total_to_be_allocated_hours = EffortHours(0)

    efforts = Table(
        Column("Hrs", justify="right"),
        Column("PtHrs", justify="right"),
        Column("TBA", justify="right"),
        Column("Adj%", justify="right"),
        Column("%eff", justify="right"),
        Column("key", justify="left"),
        Column("score", justify="left"),
    )
    for key, score in book_summary.items():
        account_name = str(key).upper()
        max_hours = 0
        for constraint in constraints_by_key.get(
            key, DistributionConstraintByAccountNameDict()
        ).values():
            match constraint:
                case HourDistributionConstraint() as hdc:
                    max_hours += hdc.max_hours
        if max_hours > 0:
            ic(key, max_hours)
        hours_equivalent = hours_per_point * score.points
        to_be_allocated_hours = EffortHours(0)
        if max_hours > 0 and hours_equivalent > max_hours:
            to_be_allocated_hours = hours_equivalent - max_hours
            hours_equivalent = max_hours
        percent_effort = (score.hours + hours_equivalent) / (
            MAX_HOURS - book_totals.auxiliary_hours
        )
        total_percent_effort += percent_effort
        total_to_be_allocated_hours += to_be_allocated_hours
        if effortable_hours > 0:
            adjusted_percent_effort = hours_equivalent / effortable_hours
            total_adjusted_percent_effort += adjusted_percent_effort
        else:
            adjusted_percent_effort = 0
        efforts.add_row(
            *effort_table_row(
                score.hours or score.auxiliary_hours,
                hours_equivalent,
                to_be_allocated_hours,
                adjusted_percent_effort,
                percent_effort,
                str(key),
                score,
            )
        )
    efforts.add_section()
    efforts.add_row(
        *effort_table_row(
            total_hours,
            effortable_hours,
            total_to_be_allocated_hours,
            total_adjusted_percent_effort,
            total_percent_effort,
            "",
            "",
        )
    )
    rprint(efforts)
    rprint(book.auxiliary_table())


def main() -> None:
    run(sys.stdin)


if __name__ == "__main__":
    main()
