from __future__ import annotations

from collections import defaultdict
from csv import DictWriter
from itertools import islice
from pathlib import Path
from sys import stdout

from dataset import Database, Table, connect
from gitlab import Gitlab
from gitlab.const import AccessLevel
from gitlab.mixins import ListMixin
from gitlab.v4.objects.groups import Group
from gitlab.v4.objects.projects import Project
from icecream import ic
from rich import inspect as ri

__ALL__ = ["main", "report_gitlab"]


DEFAULT_GITLAB_ID = None
DEFAULT_GITLAB_CONFIG_FILES = [str(Path("secrets", "gitlab.cfg"))]


def get_default_gitlab(
    *,
    gitlab_id: str | None = DEFAULT_GITLAB_ID,
    config_files: list[str] | None = DEFAULT_GITLAB_CONFIG_FILES,
) -> Gitlab:
    gl = Gitlab.from_config(gitlab_id=gitlab_id, config_files=config_files)
    gl.auth()
    return gl


def import_gitlab(gl: Gitlab, /, db_connect_url="sqlite:///:memory:") -> Database:
    db = connect(db_connect_url)
    attributes_with_lists: dict[str, set[str]] = defaultdict(set)
    group_table: Table = db["group"]
    project_table: Table = db["project"]
    for t, m in [(group_table, gl.groups), (project_table, gl.projects)]:
        t: Table = t
        m: ListMixin = m
        for o in islice(
            m.list(
                iterator=True,
                min_access_level=int(AccessLevel.REPORTER),
            ),
            5,
        ):
            row = dict()
            for k, v in o.attributes.items():
                match k, v:
                    case _, int() | str() | None:
                        row[k] = v
                    case _, list():
                        attributes_with_lists[k]
                        for item in v:
                            attributes_with_lists[k].add(repr(item))
                    case "namespace" | "_links" | "container_expiration_policy" | "permissions", _:
                        pass
                    case _:
                        raise NotImplementedError(k, v)
            t.insert(row)
    # ic(attributes_with_lists)
    return db


def report_gitlab(db: Database, /) -> None:
    for table_name in db.tables:
        t: Table = db[table_name]
        print(table_name, t.count())
        w = DictWriter(stdout, t.columns)
        w.writeheader()
        for r in t:
            w.writerow(r)


def main() -> None:
    gl = get_default_gitlab()
    db = import_gitlab(gl)
    report_gitlab(db)


if __name__ == "__main__":
    main()
