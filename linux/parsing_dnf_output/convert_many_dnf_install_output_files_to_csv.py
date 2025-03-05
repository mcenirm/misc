from __future__ import annotations

import argparse
import csv
import dataclasses
import enum
import numbers
import pathlib
import sys


class Category(enum.StrEnum):
    INDEPENDENT = enum.auto()
    DEPENDENCY = enum.auto()
    WEAK_DEPENDENCY = enum.auto()
    GROUP_OR_MODULE = enum.auto()
    REGULAR_GROUP = enum.auto()
    ENVIRONMENT_GROUP = enum.auto()

    def __init__(self, value: str):
        self.is_group = value.endswith("_group")


@dataclasses.dataclass
class Package:
    name: str
    arch: str
    version: str
    repo: str
    sizek: int
    category: Category


@dataclasses.dataclass
class Group:
    label: str
    section: Category


@dataclasses.dataclass
class TransactionSummary:
    install_count: int
    total_download: int
    installed_size: int


class Lines:
    def __init__(self, lines: list[str]):
        self.lines = tuple(lines)
        self.pos = 0

    def peek(self) -> str:
        return self.lines[self.pos]

    def incr(self) -> str:
        self.pos += 1
        return self.peek()

    def decr(self) -> str:
        self.pos -= 1
        return self.peek()

    def __len__(self):
        return len(self.lines)


POSSIBLE_TABLE_HEADERS = {
    ("Package", "Arch", "Version", "Repository", "Size"),
    ("Package", "Architecture", "Version", "Repository", "Size"),
}


class DnfInstallOutput(Lines):
    def __init__(self, goal: str, lines: list[str]):
        super().__init__([str(line).rstrip() for line in lines])
        self.goal = str(goal)

    def skip_preamble(self):
        if self.peek() == "Updating Subscription Management repositories.":
            self.incr()
        if self.peek().startswith("Last metadata expiration check: "):
            self.incr()
        if self.peek() == "Dependencies resolved.":
            self.incr()

    def skip_hr(self):
        if all(["=" == _ for _ in self.peek()]):
            self.incr()

    def skip_blank(self):
        if self.peek().strip() == "":
            self.incr()

    def read_packages(self) -> list[Package]:
        packages = []
        self.skip_hr()
        self.read_table_headers()
        self.skip_hr()
        while True:
            category = detect_category(self.peek())
            if category is None or category.is_group:
                break
            self.incr()
            while self.peek().startswith(" "):
                packages.append(self.read_package(category))
        return packages

    def read_groups(self) -> list[Group]:
        groups = []
        while True:
            category = detect_category(self.peek())
            if category is None or not category.is_group:
                break
            self.incr()
            while self.peek().startswith(" "):
                groups.append(self.read_group(category))
        return groups

    def read_summary(self):
        # TODO implement
        pass

    def read_table_headers(self):
        line = self.peek()
        if line.startswith(" "):
            words = tuple(line[1:].split())
            if words in POSSIBLE_TABLE_HEADERS:
                self.incr()
                return words
        raise ValueError("bad table header line", line)

    def read_package(self, category: Category = Category.INDEPENDENT) -> Package:
        line = self.peek()
        if line.startswith(" "):
            name = arch = version = repo = size_n = size_u = None
            try:
                name, arch, version, repo, size_n, size_u = line[1:].split()
            except ValueError:
                name = line[1:].split()
                if len(name) != 1:
                    raise ValueError("bad package precontinuation line", line)
                name = name[0]
                line = self.incr()
                if not line.startswith("  "):
                    raise ValueError("bad package continuation line", name, line)
                try:
                    arch, version, repo, size_n, size_u = line[1:].split()
                except ValueError:
                    raise ValueError("bad package continuation line", name, line)
            package = Package(
                name,
                arch,
                version,
                repo,
                size_with_unit_to_sizek(size_n, size_u),
                category,
            )
            self.incr()
            return package
        raise ValueError("bad package line", line)

    def read_group(self, category: Category = Category.REGULAR_GROUP) -> Group:
        line = self.peek()
        if line.startswith(" "):
            label = line[1:]
            group = Group(label, category)
            self.incr()
            return group
        raise ValueError("bad group line", line)


CAT_MAP = {
    "": Category.INDEPENDENT,
    "dependencies": Category.DEPENDENCY,
    "weak dependencies": Category.WEAK_DEPENDENCY,
    "group/module packages": Category.GROUP_OR_MODULE,
    "Groups": Category.REGULAR_GROUP,
    "Environment Groups": Category.ENVIRONMENT_GROUP,
}


def detect_category(line: str) -> Category | None:
    if not line.startswith("Installing"):
        return
    cat_str = line.removeprefix("Installing").removesuffix(":").strip()
    return CAT_MAP.get(cat_str, None)


UNIT_FACTORS = dict(k=1, M=1024)


def size_with_unit_to_sizek(
    size_n: numbers.Number | str, size_u: str = "k"
) -> int | float:
    size_n = int_or_float(size_n)
    sizek = size_n * UNIT_FACTORS[size_u]
    return sizek


def int_or_float(s: str) -> int | float:
    try:
        return int(s)
    except ValueError:
        return float(s)


def convert_many_dnf_install_output_files_to_csv(d: pathlib.Path):
    d = pathlib.Path(d)

    out = sys.stdout
    csv_field_names = [
        "goal",
        "goal is group?",
        "dependency is group?",
        *[f.name for f in dataclasses.fields(Package)],
        *[f.name for f in dataclasses.fields(Group)],
    ]
    writer = csv.DictWriter(out, csv_field_names, lineterminator="\n")
    writer.writeheader()

    for p in d.iterdir():
        pfilename = p.name
        goal = (
            pfilename.removesuffix(".out").removeprefix("packages.").removeprefix(".")
        )
        goal_is_group = goal.startswith("@")
        dio = DnfInstallOutput(goal, p.read_text().splitlines())
        dio.skip_preamble()
        packages = dio.read_packages()
        groups = dio.read_groups()
        dio.skip_blank()
        summary = dio.read_summary()

        writer.writerows(
            [
                {
                    csv_field_names[0]: goal,
                    csv_field_names[1]: goal_is_group,
                    csv_field_names[2]: False,
                    **dataclasses.asdict(package),
                }
                for package in packages
            ]
        )
        writer.writerows(
            [
                {
                    csv_field_names[0]: goal,
                    csv_field_names[1]: goal_is_group,
                    csv_field_names[2]: True,
                    **dataclasses.asdict(group),
                }
                for group in groups
            ]
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir_with_dnf_install_output_files")
    ns = ap.parse_args()
    convert_many_dnf_install_output_files_to_csv(
        pathlib.Path(ns.dir_with_dnf_install_output_files)
    )


if __name__ == "__main__":
    main()
