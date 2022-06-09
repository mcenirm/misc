import datetime
import unittest

import politician_ages

A = "A"
B = "B"
C = "C"
ONE = "ONE"
TWO = "TWO"
FULL_DATE = "2020-02-20"
JUST_YEAR = "2020"
JUST_YEAR_SHOULD_RESOLVE_TO = f"{JUST_YEAR}-01-01"
YEAR_MONTH = "2020-03"
YEAR_MONTH_SHOULD_RESOLVE_TO = f"{YEAR_MONTH}-01"


class TestResolve(unittest.TestCase):
    def test_resolve(self):
        data = {A: ONE, B: {C: TWO}}
        self.assertEqual(ONE, politician_ages.resolve([A], data))
        self.assertEqual(TWO, politician_ages.resolve([B, C], data))


class TestCoerceToDate(unittest.TestCase):
    def test_coerce_to_date_full_date(self):
        self.assertEqual(
            FULL_DATE, date_as_str(politician_ages.coerce_to_date(FULL_DATE))
        )

    def test_coerce_to_date_year_month(self):
        self.assertEqual(
            YEAR_MONTH_SHOULD_RESOLVE_TO,
            date_as_str(politician_ages.coerce_to_date(YEAR_MONTH)),
        )

    def test_coerce_to_date_just_year(self):
        self.assertEqual(
            JUST_YEAR_SHOULD_RESOLVE_TO,
            date_as_str(politician_ages.coerce_to_date(JUST_YEAR)),
        )


class TestCoerceToYear(unittest.TestCase):
    def test_coerce_to_year_full_date(self):
        self.assertEqual(int(FULL_DATE[:4]), politician_ages.coerce_to_year(FULL_DATE))

    def test_coerce_to_year_year_month(self):
        self.assertEqual(
            int(YEAR_MONTH[:4]), politician_ages.coerce_to_year(YEAR_MONTH)
        )

    def test_coerce_to_year_just_year(self):
        self.assertEqual(int(JUST_YEAR[:4]), politician_ages.coerce_to_year(JUST_YEAR))


def date_as_str(d: datetime.date) -> str:
    return d.strftime("%F")


if __name__ == "__main__":
    unittest.main()
