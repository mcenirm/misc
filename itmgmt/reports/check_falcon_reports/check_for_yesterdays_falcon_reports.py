import collections
import configparser
import csv
import datetime
import hashlib
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import urllib.parse
from enum import Flag, auto
from pathlib import Path
from typing import Any, List, Mapping, Tuple, Union

FINGERPRINT = hashlib.sha256(open(__file__, "br").read()).digest()

CHECK_FALCON_REPORTS_SETTINGS_ATTRIBUTE_NAMES = [
    "access_log",
    "date_expression",
    "database",
]
CHECK_FALCON_REPORTS_SETTINGS_SECTION_NAME = "settings"

StrOrBytesPath = Union[str, bytes, "os.PathLike[str]", "os.PathLike[bytes]"]


class CheckFalconReportsSettings:
    access_log: Path
    date_expression: str = "yesterday"
    database: StrOrBytesPath

    def __init__(self, name="check_falcon_reports", argv=[]):
        self._name = name
        config = configparser.ConfigParser()
        files = guess_config_files(name)
        logging.debug("files: %r", files)
        config.read(files)
        logging.debug(
            "from files: %s", dict(config[CHECK_FALCON_REPORTS_SETTINGS_SECTION_NAME])
        )
        args, kwargs = config_from_argv(argv)
        logging.debug("from argv: %r %r ", args, kwargs)
        combined = {**config[CHECK_FALCON_REPORTS_SETTINGS_SECTION_NAME], **kwargs}
        for attrname in CHECK_FALCON_REPORTS_SETTINGS_ATTRIBUTE_NAMES:
            if attrname in combined:
                setattr(self, attrname, combined[attrname])
        if args:
            self.date_expression = args[0]
        if not getattr(self, "database", None):
            self.database = guess_database_file(name)
        for attrname in CHECK_FALCON_REPORTS_SETTINGS_ATTRIBUTE_NAMES:
            value = getattr(self, attrname)
            logging.debug("%s: %s", attrname, value)


class Record(dict):
    FIELD_LABELS = collections.OrderedDict(
        result="Result",
        computer="Computer",
        ip="IP",
        user="User",
        date="Date",
        time="Time",
        zone="Zone",
        psbuild="PSBuild",
        tagged="Tagged?",
        tag="Tag",
        model="Model",
        osversion="OS",
        serial="Serial",
    )


class HistorySaveFlag(Flag):
    RECORDS_ONLY = 0
    MATCHED_LINES = auto()
    UNMATCHED_LINES = auto()
    PARSED_LINES = auto()
    UNPARSED_LINES = auto()
    ALL_LINES = MATCHED_LINES | UNMATCHED_LINES | PARSED_LINES | UNPARSED_LINES


class History:
    @property
    def all_lines(self) -> List[str]:
        return self._lines[HistorySaveFlag.ALL_LINES]

    @property
    def unparsed_lines(self) -> List[str]:
        return self._lines[HistorySaveFlag.UNPARSED_LINES]

    @property
    def parsed_lines(self) -> List[str]:
        return self._lines[HistorySaveFlag.PARSED_LINES]

    @property
    def matched_lines(self) -> List[str]:
        return self._lines[HistorySaveFlag.MATCHED_LINES]

    @property
    def unmatched_lines(self) -> List[str]:
        return self._lines[HistorySaveFlag.UNMATCHED_LINES]

    @property
    def records(self) -> List[Record]:
        return self._records

    def __init__(
        self,
        date_filter: str,
        lines_to_save=HistorySaveFlag.RECORDS_ONLY,
        err=None,
    ) -> None:
        self._lines = {}
        for flag in HistorySaveFlag:
            self._lines[flag] = []
        self._records = self._lines[HistorySaveFlag.RECORDS_ONLY]
        self.date_filter = date_filter
        self.lines_to_save = lines_to_save
        self.err = err

    def _save_line(self, flag: HistorySaveFlag, line: str) -> None:
        if (self.lines_to_save & flag) == flag:
            self._lines[flag].append(line)

    def read_records_from_logs(self, *logs):
        lognames = dict([(_, os.path.basename(_)) for _ in logs])
        for line, line_no, log_filename in lines_from_log_files(*logs):
            self._save_line(HistorySaveFlag.ALL_LINES, line)
            d = parse(line)
            if d:
                self._save_line(HistorySaveFlag.PARSED_LINES, line)
                if d["t"].startswith(self.date_filter) and d["r"].lower().startswith(
                    "get /falcon-report.txt?"
                ):
                    self._save_line(HistorySaveFlag.MATCHED_LINES, line)

                    t_date, t_time = d["t"].split(":", 1)
                    t_time, t_zone = t_time.split(None, 1)

                    lead, psbuild = d["user_agent"].rsplit("/", 1)
                    if not lead.lower().endswith("powershell"):
                        psbuild = "n/a"

                    record = Record(
                        recordid="{0}:{1}".format(lognames[log_filename], line_no),
                        timestamp=d["timestamp"],
                        ip=d["h"],
                        user=d["u"],
                        date=t_date,
                        time=t_time,
                        zone=t_zone,
                        psbuild=psbuild,
                        tagged="untagged",
                    )

                    method, rest = d["r"].split(None, 1)
                    path, rest = rest.rsplit(None, 1)
                    query = urllib.parse.urlparse(path, "http").query
                    data = urllib.parse.parse_qs(query)

                    for k in data.keys():
                        v = data[k][0]
                        if k == "tag":
                            record["tagged"] = "tagged"
                        elif k == "computer" and "." in v:
                            v = v.split(".")[0]
                        record[k] = v
                        if not k in Record.FIELD_LABELS:
                            if self.err:
                                print("## unexpected parameter:", k, file=self.err)
                            Record.FIELD_LABELS[k] = k

                    self.records.append(record)
                else:
                    self._save_line(HistorySaveFlag.UNMATCHED_LINES, line)
            else:
                self._save_line(HistorySaveFlag.UNPARSED_LINES, line)


class Database:
    def __init__(self, column_names: List[str]) -> None:
        self.table_name = "records"
        self.pk_name = "recordid"
        self.ts_name = "timestamp"
        self.column_names = list(column_names)

    def _repair_records_schema(self):
        ctx = self._new_context()
        if not self._does_records_table_exist(ctx):
            self._create_records_table(ctx)
        existings = self._get_records_table_column_names(ctx)
        missings = set(self.column_names).difference(set(existings))
        for missing in missings:
            self._add_records_column(ctx, missing)
        self._dispose_context(ctx)

    def _new_context(self) -> Any:
        raise NotImplementedError()

    def _does_records_table_exist(self, ctx: Any) -> bool:
        raise NotImplementedError()

    def _create_records_table(self, ctx: Any) -> None:
        raise NotImplementedError()

    def _get_records_table_column_names(self, ctx: Any) -> List[str]:
        raise NotImplementedError()

    def _add_records_column(self, ctx: Any, column_name: str) -> None:
        raise NotImplementedError()

    def _dispose_context(self, ctx: Any) -> None:
        raise NotImplementedError()

    def upsert(self, records: List[Record]) -> None:
        raise NotImplementedError()


class Sqlite3Database(Database):
    def __init__(self, database: StrOrBytesPath, column_names: List[str]) -> None:
        super().__init__(column_names)
        self.database = database
        self._connect()
        self._repair_records_schema()

    def _connect(self):
        if not str(self.database).startswith(":"):
            Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(
            self.database,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )

    def _new_context(self) -> sqlite3.Cursor:
        return self.connection.cursor()

    def _does_records_table_exist(self, ctx: sqlite3.Cursor) -> bool:
        if sqlite3.sqlite_version_info < (3, 30, 0):
            schema_table_name = "sqlite_master"
        else:
            schema_table_name = "sqlite_schema"
        sql = "SELECT name FROM {0:s} WHERE type = 'table' AND name = ?".format(
            schema_table_name
        )
        logging.debug("does records table exist: %r", sql)
        matching_tables = ctx.execute(sql, (self.table_name,)).fetchall()
        if not matching_tables:
            return False
        if len(matching_tables) > 1:
            logging.warning(
                "expected 1 records table, got %d: %s",
                len(matching_tables),
                self.table_name,
            )
        return True

    def _create_records_table(self, ctx: sqlite3.Cursor) -> None:
        sql = (
            "CREATE TABLE {0:s} ({1:s} TEXT PRIMARY KEY, {2:s} TIMESTAMP{3:s})".format(
                self.table_name,
                self.pk_name,
                self.ts_name,
                "".join([", {0:s} TEXT".format(_) for _ in self.column_names]),
            )
        )
        logging.debug("create records table: %r", sql)
        ctx.execute(sql)

    def _get_records_table_column_names(self, ctx: sqlite3.Cursor) -> List[str]:
        sql = "PRAGMA table_info('{0:s}')".format(self.table_name)
        logging.debug("get records table column names: %r", sql)
        results = ctx.execute(sql).fetchall()
        names = [_[1] for _ in results]
        return names

    def _add_records_column(self, ctx: sqlite3.Cursor, column_name: str) -> None:
        sql = "ALTER TABLE {0:s} ADD COLUMN {1:s} TEXT".format(
            self.table_name, column_name
        )
        logging.debug("add records column: %r", sql)
        ctx.execute(sql)

    def _dispose_context(self, ctx: sqlite3.Cursor) -> None:
        ctx.close()

    def upsert(self, records: List[Record]) -> None:
        non_pk_names = [self.ts_name] + self.column_names
        names = [self.pk_name] + non_pk_names
        sql_center = "INTO {0}({1}) VALUES({2})".format(
            self.table_name,
            ",".join(names),
            ",".join(["?"] * len(names)),
        )
        if sqlite3.sqlite_version_info < (3, 24, 0):
            sql = "INSERT OR REPLACE {0}".format(sql_center)
        else:
            sql = "INSERT {0} ON CONFLICT({1}) DO UPDATE SET {2}".format(
                sql_center,
                self.pk_name,
                ",".join(["{0}=excluded.{0}".format(_) for _ in non_pk_names]),
            )
        logging.debug("upsert: %r", sql)
        with self.connection:
            self.connection.executemany(
                sql,
                [[record.get(_, None) for _ in names] for record in records],
            )


class XDG:
    """
    data_dir:     .local/share/{{NAME}}    $XDG_DATA_HOME/{{NAME}}
    config_dir:   .config/{{NAME}}         $XDG_CONFIG_HOME/{{NAME}}
    cache_dir:    .cache/{{NAME}}          $XDG_CACHE_HOME/{{NAME}}
    state_dir:    .local/state/{{NAME}}    $XDG_STATE_HOME/{{NAME}}
    log_dir:      .cache/{{NAME}}/log
    runtime_dir:                           $XDG_RUNTIME_DIR
    """

    @staticmethod
    def _base(
        xdg_env_var: str, base_dir_name: str, is_relative_to_home: bool = True
    ) -> str:
        default = base_dir_name
        if is_relative_to_home:
            default = os.path.join(os.environ["HOME"], base_dir_name)
        return os.environ.get(xdg_env_var, default)

    @staticmethod
    def config_base() -> str:
        return XDG._base("XDG_CONFIG_HOME", ".config")

    @staticmethod
    def config_dir(app_name: str) -> str:
        return os.path.join(XDG.config_base(), app_name)

    @staticmethod
    def config_file(app_name: str, config_file_name: str = "config") -> str:
        return os.path.join(XDG.config_dir(app_name), config_file_name)

    @staticmethod
    def state_base() -> str:
        return XDG._base("XDG_STATE_HOME", os.path.join(".local", "state"))

    @staticmethod
    def state_dir(app_name: str) -> str:
        return os.path.join(XDG.state_base(), app_name)


def main():
    argv = sys.argv
    if len(argv) > 1 and argv[1] == "--debug":
        logging.basicConfig(level=logging.DEBUG)
        argv = argv[:1] + argv[2:]
    settings = CheckFalconReportsSettings(argv=argv)
    return run(settings)


def run(
    settings: CheckFalconReportsSettings,
    out=sys.stdout,
    err=sys.stderr,
) -> int:
    date_of_interest = get_date_for_expression(settings.date_expression)
    date_filter = determine_date_filter(date_of_interest)
    logs = determine_log_filenames(settings.access_log, date_of_interest)

    history = History(date_filter, err=err)
    history.read_records_from_logs(*logs)

    if history.unparsed_lines:
        print(history.unparsed_lines[0], file=err)
        return 1
    if history.records:
        write_records_as_csv(history.records, out=out)
        db = Sqlite3Database(settings.database, Record.FIELD_LABELS.keys())
        db.upsert(history.records)
    return 0


def write_records_as_csv(
    records: List[Record],
    field_label_map: Mapping[str, str] = Record.FIELD_LABELS,
    restval="n/a",
    extrasaction="ignore",
    out=sys.stdout,
) -> None:
    writer = csv.DictWriter(
        out,
        field_label_map.keys(),
        restval=restval,
        extrasaction=extrasaction,
    )
    writer.writerow(field_label_map)
    writer.writerows(
        [
            dict([(k, apostrophize_number_as_text(v)) for k, v in r.items()])
            for r in records
        ]
    )


def config_from_argv(argv: List[str]) -> Tuple[List[str], Mapping[str, Any]]:
    argv = argv[1:]
    kwargs = {}
    args = []
    while argv:
        arg = argv.pop(0)
        if arg == "--":
            args = argv
            break
        if arg.startswith("-"):
            arg = arg.lstrip("-")
            if arg.startswith("no-"):
                name = arg[3:]
                value = False
            elif "=" in arg:
                name, value = arg.split("=", 1)
            else:
                value = True
            name = name.replace("-", "_")
            kwargs[name] = value
        else:
            args.append(arg)
    return args, kwargs


def guess_something_files(
    app_name: str,
    something_name: str,
    ext: str = None,
    specific_files: List[str] = [],
) -> List[str]:
    from_env = os.environ.get((app_name + "_" + something_name).upper())
    if ext:
        suffix = ext
    else:
        suffix = ("_" if "_" in app_name else "") + something_name
    from_home = os.path.join(os.environ["HOME"], "." + app_name.lower() + suffix)
    guesses = list(filter(bool, [from_env, *specific_files, from_home]))
    return guesses


def guess_config_files(app_name: str) -> List[str]:
    return guess_something_files(
        app_name,
        "config",
        specific_files=[XDG.config_file(app_name)],
    )


def guess_database_files(app_name: str) -> List[str]:
    return guess_something_files(
        app_name,
        "db",
        ext=".db",
        specific_files=[os.path.join(XDG.state_dir(app_name), "history.db")],
    )


def guess_database_file(app_name: str) -> str:
    guessed = guess_database_files(app_name)
    existing = [_ for _ in guessed if Path(_).is_file()]
    return (existing if existing else guessed)[0]


def determine_defaults():
    config_file = find_config_file()
    config = load_config_from_file(config_file)
    date_expression = config.get("date_expression", "yesterday")
    access_log = config["access_log"]
    return date_expression, access_log


def load_config_from_file(config_file):
    config = {}
    with open(config_file) as f:
        lines = f.readlines()
    for line in lines:
        line = str(line).strip()
        if not line or line.startswith("#"):
            continue
        try:
            name, value = line.split(":", 1)
        except ValueError:
            continue
        name = name.strip()
        value = value.strip()
        config[name] = value
    return config


def find_config_file(app_name="falcon_reports"):
    config_home = os.environ.get("XDG_CONFIG_HOME")
    if not config_home:
        config_home = os.path.join(os.environ["HOME"], ".config")
    config_file = os.path.join(config_home, app_name + ".cfg")
    return config_file


def find_gnu_date():
    gdate = [_ for _ in ["gdate", "date"] if shutil.which(_)][0]
    return gdate


def determine_date_filter(date: datetime.date) -> str:
    return date.strftime("%d/%b/%Y")


def get_date_for_expression(date_expression: str) -> datetime.date:
    gdate = find_gnu_date()
    dd_mm_yyyy = (
        subprocess.Popen(
            [
                gdate,
                "-d",
                date_expression,
                "+%d/%b/%Y",
            ],
            stdout=subprocess.PIPE,
            universal_newlines=True,
        )
        .communicate()[0]
        .strip()
    )
    return datetime.datetime.strptime(dd_mm_yyyy, "%d/%b/%Y").date()


def determine_log_filenames(access_log: str, today: datetime.date) -> Tuple[str, str]:
    yesterday = today - datetime.timedelta(days=1)
    logs = [
        "{0}.{1}".format(access_log, _.strftime("%Y_%b")) for _ in (yesterday, today)
    ]
    if logs[0] == logs[1]:
        del logs[1]
    return tuple(logs)


def lines_from_log_files(*filenames) -> Tuple[str, int, str]:
    for fn in filenames:
        with open(fn) as f:
            for i, line in enumerate(f):
                yield line, i, fn


def pat(name, pattern):
    return "(?P<" + name + ">" + pattern + ")"


def pat_escaped_string(name):
    return '"' + pat(name, r'(?:\\"|[^"])*') + '"'


def pat_timestamp(name):
    return r"\[" + pat(name, r"../.../....:..:..:.. .....") + r"\]"


# from httpd.conf
# LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-Agent}i\"" combined
COMBINED_LOG_PATTERN = (
    "^"
    + " ".join(
        [
            pat("h", r"\S+"),
            "-",
            pat("u", r".*?"),
            pat_timestamp("t"),
            pat_escaped_string("r"),
            pat("s", r"\d+"),
            pat("b", r"-|\d+"),
            pat_escaped_string("referer"),
            pat_escaped_string("user_agent"),
        ]
    )
    + "$"
)
COMBINED_LOG_RE = re.compile(COMBINED_LOG_PATTERN)


def parse(line):
    d = {}
    m = COMBINED_LOG_RE.match(line)
    if m:
        d = m.groupdict()
        d["timestamp"] = datetime.datetime.strptime(d["t"], "%d/%b/%Y:%H:%M:%S %z")
    return d


LOOKS_LIKE_A_NUMBER_RE = re.compile(r"^[-+]?[,.0-9]+$")


def apostrophize_number_as_text(n):
    s = str(n).strip()
    if LOOKS_LIKE_A_NUMBER_RE.match(s):
        return "'" + s
    else:
        return n


if __name__ == "__main__":
    sys.exit(main())
