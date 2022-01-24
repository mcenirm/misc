import ast
import datetime
import math
import re
import string
import sys
from dataclasses import dataclass
from logging import warning
from numbers import Number
from typing import TextIO, Type, Union
from urllib.parse import urlparse

from icecream import ic
from rich import inspect as rinspect
from rich import print as rprint


def _build_abbreviations(fmt: str, incr_days: int) -> set[str]:
    if not getattr(_build_abbreviations, "start", None):
        # The first day of 2001 was a Monday, but this is arbitrary.
        _build_abbreviations.start = datetime.datetime.strptime(
            "2001-01-01",
            "%Y-%m-%d",
        ).date()
    abbreviations = set()
    delta = datetime.timedelta(days=incr_days)
    day = _build_abbreviations.start
    while (abbr := day.strftime(fmt).upper()) not in abbreviations:
        abbreviations.add(abbr)
        day += delta
    return abbreviations


WEEKDAY_ABBREVIATIONS = _build_abbreviations("%a", 1)
MONTH_ABBREVIATIONS = _build_abbreviations("%b", 31)

MAX_HOURS = 80
SPREADSHEET_URL_PREFIX = "https://docs.google.com/spreadsheets/d/"
RE_NUMBER_OF_HOURS = re.compile(
    r"\b(?P<number_of_hours>\d+(?:[.,]\d+)?)\s*h(?:ou)?rs?\b",
    re.IGNORECASE,
)


class DayParser:
    def __init__(self, __format: str) -> None:
        self._format_handles_year = self._does_day_format_handle_year(__format)
        if self.format_handles_year:
            self._format = __format
        else:
            self._format = "%Y {0}".format(__format)

    @property
    def format(self):
        return self._format

    @property
    def format_handles_year(self):
        return self._format_handles_year

    def parse_day(self, day: str) -> Union[datetime.date, None]:
        if self.format_handles_year:
            return self._parse_day(day)
        else:
            return self._parse_day_by_guessing_year(day)

    def _parse_day(self, day: str) -> Union[datetime.date, None]:
        try:
            return self._strpdate(day, self.format)
        except ValueError:
            return None

    def _parse_day_by_guessing_year(self, day: str) -> Union[datetime.date, None]:
        today = datetime.date.today()
        guesses = []
        for dy in [-1, 0, +1]:
            year_and_day = "{0} {1}".format(today.year + dy, day)
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
    def _strpdate(__date_string: str, __format: str) -> datetime.date:
        return datetime.datetime.strptime(__date_string, __format).date()

    @staticmethod
    def _does_day_format_handle_year(__format: str) -> bool:
        today = datetime.date.today()
        today_as_string = today.strftime(__format)
        reparsed_today = DayParser._strpdate(today_as_string, __format)
        return today == reparsed_today


DAY_PARSER = DayParser("%a %b %d")
DAY_ENTRY_PARTS_SEPARATOR = " - "


@dataclass(frozen=True)
class DistributionConstraint:
    distribution_account_name: str

    @classmethod
    def from_spec(
        cls: Type["DistributionConstraint"],
        spec: str,
        /,
    ) -> Union["DistributionConstraint", None]:
        raise NotImplementedError()


@dataclass(frozen=True)
class PercentEffortDistributionConstraint(DistributionConstraint):
    min_percent: Number
    max_percent: Number


@dataclass(frozen=True)
class HourDistributionConstraint(DistributionConstraint):
    min_hours: Number
    max_hours: Number

    @classmethod
    def from_spec(
        cls: Type["HourDistributionConstraint"],
        spec: str,
        /,
    ) -> Union["HourDistributionConstraint", None]:
        before_and_hours_and_after = RE_NUMBER_OF_HOURS.split(spec, maxsplit=1)
        if len(before_and_hours_and_after) != 3:
            return None
        before, number_of_hours, after = before_and_hours_and_after
        after = after.lstrip(string.punctuation).strip()
        o = cls(after, 0, ast.literal_eval(number_of_hours))
        return o


@dataclass(frozen=True)
class RemainderDistributionConstraint(DistributionConstraint):
    @classmethod
    def from_spec(
        cls: Type["RemainderDistributionConstraint"],
        spec: str,
        /,
    ) -> Union["RemainderDistributionConstraint", None]:
        words = spec.split()
        if not words:
            return None
        if words[0] in ("rest", "remainder", "else"):
            spec = spec.removeprefix(words[0]).strip()
            words.pop(0)
        if words:
            name = spec
            o = cls(name)
            return o
        else:
            return None


@dataclass(frozen=True)
class Entry:
    key: str

    @classmethod
    def from_spec(
        cls: Type["Entry"],
        spec: str,
        /,
    ) -> Union["Entry", None]:
        raise NotImplementedError()


@dataclass(frozen=True)
class PointsEntry(Entry):
    points: Number

    @classmethod
    def from_spec(
        cls: Type["PointsEntry"],
        spec: str,
        /,
    ) -> Union["PointsEntry", None]:
        try:
            key_and_points = spec.split(maxsplit=1)
            key = key_and_points[0].strip().lower()
            points = ast.literal_eval(key_and_points[1])
            assert isinstance(points, Number)
            return cls(key, points)
        except ValueError:
            return None


@dataclass(frozen=True)
class HoursEntry(Entry):
    hours: Number

    @classmethod
    def from_spec(
        cls: Type["HoursEntry"],
        spec: str,
        /,
    ) -> Union["HoursEntry", None]:
        before_and_hours_and_after = RE_NUMBER_OF_HOURS.split(spec, maxsplit=1)
        if len(before_and_hours_and_after) != 3:
            return None
        key = before_and_hours_and_after[0].strip().lower()
        hours = ast.literal_eval(before_and_hours_and_after[1])
        return cls(key, hours)


class Book:
    def __init__(self) -> None:
        self.distribution_constraints_by_entry_key = {}
        self.entries_by_day_and_key = {}

    def constrain(
        self,
        entry_key: str,
        constraints: set[DistributionConstraint],
        /,
        context_description_in_case_of_error: str = "",
    ) -> None:
        if entry_key in self.distribution_constraints_by_entry_key:
            if context_description_in_case_of_error:
                context_description_in_case_of_error = (
                    " " + context_description_in_case_of_error.lstrip()
                )
            raise ValueError(
                "distribution constraint key {0} reused{1}".format(
                    repr(entry_key),
                    context_description_in_case_of_error,
                )
            )
        else:
            self.distribution_constraints_by_entry_key[entry_key] = constraints

    def add_day_entries(self, day: datetime.date, entries: list[Entry]) -> None:
        for entry in entries:
            self.add_entry(day, entry)

    def add_entry(self, day: datetime.date, entry: Entry) -> None:
        t = (day, entry.key)
        if t in self.entries_by_day_and_key:
            raise ValueError("already saw day-key entry: {0}".format(t))
        self.entries_by_day_and_key[t] = entry


def parse_as_spreadsheet_url(line: str, /) -> Union[str, None]:
    if line.startswith(SPREADSHEET_URL_PREFIX):
        result = urlparse(line)
        return result.geturl()
    else:
        return None


def parse_as_entry_key_and_distribution_constraint_set(
    line: str,
    /,
) -> Union[tuple[str, set[DistributionConstraint]], None]:
    key_and_specs = line.split(":", maxsplit=1)
    if len(key_and_specs) == 1:
        return None
    else:
        key = key_and_specs[0].lower()
        spec_list = [str(_).strip() for _ in key_and_specs[1].split(";")]
        constraints = set()
        for spec in spec_list:
            for cls in [HourDistributionConstraint, RemainderDistributionConstraint]:
                from_spec = getattr(cls, "from_spec")
                constraint = from_spec(spec)
                if constraint:
                    constraints.add(constraint)
                    break
        return key, constraints


def parse_as_day_and_entry_list(
    line: str,
    /,
) -> tuple[datetime.date, list[Entry]]:
    day_and_entry_list = list(line.split(DAY_ENTRY_PARTS_SEPARATOR))
    if len(day_and_entry_list) < 2:
        return None
    day = DAY_PARSER.parse_day(day_and_entry_list[0])
    if not day:
        return None
    entry_list = []
    for entry_spec in day_and_entry_list[1:]:
        for cls in [HoursEntry, PointsEntry]:
            from_spec = getattr(cls, "from_spec")
            entry = from_spec(entry_spec)
            if entry:
                entry_list.append(entry)
                break
    if entry_list:
        return day, entry_list
    else:
        return None


def load(infile: TextIO, book: Book) -> None:
    for line_num, line in enumerate([""] + [str(_).strip() for _ in infile]):
        if not line:
            continue
        elif url := parse_as_spreadsheet_url(line):
            warning("see spreadsheet at %s", url)
        elif key_and_set := parse_as_entry_key_and_distribution_constraint_set(line):
            key, dcs = key_and_set
            book.constrain(key, dcs, "at line {0}".format(line_num))
        elif day_and_entries := parse_as_day_and_entry_list(line):
            day, entries = day_and_entries
            book.add_day_entries(day, entries)
        else:
            unabsorbed = line
            ic(unabsorbed)


def run(stdin, /) -> None:
    book = Book()
    load(stdin, book)
    ic(book.distribution_constraints_by_entry_key)
    ic(book.entries_by_day_and_key)


def main() -> None:
    run(sys.stdin)


if __name__ == "__main__":
    main()
