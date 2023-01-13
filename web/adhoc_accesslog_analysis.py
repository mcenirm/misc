from __future__ import annotations

import bz2
import csv
import gzip
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from textwrap import dedent


def exec_and_fetchall(connection: sqlite3.Connection, sql: str) -> list:
    cursor = connection.cursor()
    cursor.execute(sql)
    return cursor.fetchall()


def select_from_schema(
    connection: sqlite3.Connection,
    result_phrase: str,
    clause_phrase: str = "",
) -> list:
    sql = f"SELECT {result_phrase} FROM main.sqlite_schema {clause_phrase}"
    return exec_and_fetchall(connection, sql)


def get_table_list(connection: sqlite3.Connection) -> list:
    return select_from_schema(connection, "name, sql", "WHERE type='table'")


def csv_kwargs_from_headerline(headerline: str) -> None:
    kwargs = dict(
        delimiter="\t",
        quotechar=None,
        escapechar=None,
        doublequote=False,
        quoting=csv.QUOTE_NONE,
    )
    fieldnames = []
    for name in map(str.lower, next(csv.reader([headerline], **kwargs))):
        assert name.isidentifier(), f"ugly fieldname: {name!r}"
        fieldnames.append(name)
    kwargs["fieldnames"] = fieldnames
    return kwargs


table_name = "access"
file_col = "log"
line_col = "line"
pk_list = [file_col, line_col]
pk_phrase = ", ".join(pk_list)

dbpath = Path(sys.argv[1])
with sqlite3.connect(dbpath) as con:
    for logtxtpath in map(Path, sys.argv[2:]):
        match logtxtpath.suffix.lower():
            case ".gz":
                logtxtfile = gzip.open(logtxtpath, "rt")
            case ".bz2":
                logtxtfile = bz2.open(logtxtpath, "rt")
            case _:
                logtxtfile = open(logtxtpath, "rt")
        with logtxtfile:
            log = logtxtpath.stem
            headerline = logtxtfile.readline()
            reader = csv.DictReader(
                logtxtfile,
                **csv_kwargs_from_headerline(headerline),
            )
            col_phrase = ", ".join(pk_list + reader.fieldnames)
            ph_phrase = ", ".join(["?"] * (len(pk_list) + len(reader.fieldnames)))
            create_table_sql = dedent(
                f"""\
                CREATE TABLE IF NOT EXISTS {table_name}(
                    {col_phrase},
                    PRIMARY KEY (
                        {pk_phrase}
                    )
                )
                """
            )
            replace_sql = dedent(
                f"""\
                REPLACE INTO {table_name}(
                    {col_phrase}
                )
                VALUES (
                    {ph_phrase}
                )
                """
            )
            with closing(con.cursor()) as cur:
                cur.execute(create_table_sql)

            print("-" * 40)
            for name, type_, sql in select_from_schema(con, "name, type, sql"):
                print(f"-- {type_}: {name}")
                if sql is not None:
                    print(f"{sql};")
            print("-" * 40)

            with closing(con.cursor()) as cur:
                for i, row in enumerate(reader):
                    values = [log, i + 1] + [row[name] for name in reader.fieldnames]
                    cur.execute(replace_sql, values)

        print(exec_and_fetchall(con, f"SELECT COUNT(*) from {table_name}")[0][0])
        print(
            exec_and_fetchall(
                con,
                f"SELECT * from {table_name} ORDER BY {file_col} DESC, {line_col} DESC LIMIT 1",
            )
        )
