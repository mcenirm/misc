from __future__ import annotations

import abc
import csv
import dataclasses
import datetime
import functools
import json
import os
import pathlib
import platform
import re
import sys
import typing


@dataclasses.dataclass(frozen=True, kw_only=True)
class LogEntry:
    linenum: int
    timestamp: str
    module: str
    function: str
    thread_id: str
    file: str
    line: str
    level: str
    message: str
    labels: set[str] = dataclasses.field(default_factory=set)
    arguments: dict[str, str] = dataclasses.field(default_factory=dict)
    parameters: dict[str, str] = dataclasses.field(default_factory=dict)
    extras: dict[str, str] = dataclasses.field(default_factory=dict)

    @functools.cached_property
    def timestamp_dt(self) -> datetime.datetime:
        return datetime.datetime.strptime(self.timestamp, "%a %b %d %H:%M:%S.%f %Y")

    @functools.cached_property
    def message_without_parameters(self) -> str:
        for sw, ew in {
            "cscan": [
                ("Failed with json out as ", ""),
                ("Json in as ", ""),
                ("Json out as ", ""),
            ],
        }.get(self.module, []):
            if self.message.startswith(sw) and self.message.endswith(ew):
                self.parameters["json"] = json.loads(
                    self.message.removeprefix(sw).removesuffix(ew)
                )
                self.labels.add("json")
                return sw + "…" + ew

        for label, sw, ew, pat, repl in {
            "cscan": [
                (
                    "certinfo",
                    "certinfo[",
                    "]",
                    r"(?P<n>\w+)(=\()(?P<v>[^)]*)(\))",
                    r"\1\2…\4",
                ),
                (
                    "fingerprints",
                    "Fingerprints match: ",
                    "",
                    r"\b(?P<n>Given|Computed)(\()(?P<v>[0-9A-F]{40})(\))",
                    r"\1\2…\4",
                ),
                (
                    "found",
                    "found ",
                    "",
                    r"(?P<n>[^(]+)( \()(?P<v>[^)]*)(\))",
                    r"\1\2…\4",
                ),
                (
                    "found",
                    "detected ",
                    "",
                    r"(?P<n>[^(]+)(: \()(?P<v>[^)]*)(\))",
                    r"\1\2…\4",
                ),
                (
                    "colon-paren",
                    "",
                    "",
                    r"(?P<n>[^:]+?)(: \()(?P<v>[^)]*)(\)\.?)",
                    r"\1\2…\4",
                ),
                # XX ("equal-bracket", "", "", r"([:,] )(?P<n>\w+)( = \[)(?P<v>[^]]*)(\])", r"\1\2\3…\5"),
                # XX ("equal-bracket", "","",r"([:,] \w+ = \[)[^]]*(\])", r"\1…"),
                ("equal", "", "", r"([.,] )(?P<n>\w+)( = )(?P<v>[^,]*)", r"\1\2\3…\4"),
                # XX ("equal", "","",r"([.,] \w+ = )[^,]*", r"\1…"),
            ],
            "libcsd": [
                (
                    "connection",
                    "*** ",
                    " ***",
                    r"(new |reset )(?P<n>connection)( \[)(?P<v>[0-9a-f]+)(\] from pid: \[\d+\])",
                    r"\1\2\3…\5",
                ),
            ],
        }.get(self.module, []) + [
            ("date", "", "", r"(?P<n>Date)(: )(?P<v>.*)", r"\1\2…"),
        ]:
            if self.message.startswith(sw) and self.message.endswith(ew):
                pat = re.compile(pat)
                mwp = (
                    sw
                    + pat.sub(repl, self.message.removeprefix(sw).removesuffix(ew))
                    + ew
                )
                if mwp != self.message:
                    break
        else:
            return self.message

        self.labels.add(label)

        for m in pat.finditer(self.message):
            n = m.group("n")
            v = m.group("v")
            if n in self.parameters:
                raise KeyError(
                    "parameter already exists",
                    dict(n=n, newv=v, oldv=self.parameters[n], entry=self),
                )
            self.parameters[n] = v

        return mwp

    @functools.cached_property
    def message_without_digits(self) -> str:
        return re.sub(r"\d+", "·", self.message)

    @classmethod
    def from_line(cls, linenum: int, line: str) -> typing.Self | None:
        m_line = re.compile(
            r"\[(?P<timestamp>[^]]+)\]"
            + r"\[(?P<module>[^]]+)\]"
            + r"Function: (?P<function>.*?)"
            + r" Thread Id: (?P<thread_id>.*?)"
            + r" File: (?P<file>.*?)"
            + r" Line: (?P<line>.*?)"
            + r" Level: (?P<level>.*?)"
            + r" :(?P<message>.*)"
        ).match(line)
        if m_line:
            return cls(linenum=linenum, **m_line.groupdict())
        else:
            return None


class CodeModule:
    def __init__(self):
        self.hello = None
        self.entries = []

    @abc.abstractmethod
    def add(self, entry: LogEntry):
        self._check(entry)

    @classmethod
    @abc.abstractmethod
    def _check(cls, entry: LogEntry):
        if entry is None:
            raise ValueError("unexpected None", dict(cls=cls))
        raise ValueError("unexpected entry", dict(cls=cls, entry=entry))


class CScan(CodeModule):
    pass


class LibCSD(CodeModule):
    pass


class Session:
    def __init__(self):
        self.modules = {}

    def add(self, entry: LogEntry) -> typing.Self | Session:
        # TODO check what ends a session and return a new session
        return self

    def get_module(self, module_name: str) -> CodeModule | None:
        if module_name is None:
            return None
        module_name = str(module_name).lower()

        if module_name in self.modules:
            return self.modules[module_name]

        for cls in CodeModule.__subclasses__():
            if cls.__name__.lower() == module_name:
                self.modules[module_name] = cls()
                return self.modules[module_name]

        return None


LOG_FILE_PAT = re.compile(r"(?P<base>(cscan|libcsd)\.log)(\.\d+)?$")


def analyze_hostscan_log(logpath: pathlib.Path):
    logpath = pathlib.Path(logpath)
    lines = logpath.read_text().splitlines()

    entries: list[LogEntry] = []

    for linenum, line in enumerate(lines, 1):
        entry = LogEntry.from_line(linenum, line)
        if entry:
            entries.append(entry)
        else:
            raise ValueError(
                "Unrecognized line", dict(logpath=logpath, linenum=linenum, line=line)
            )

    if not entries:
        return

    csvbasename = logpath.name
    m_log = LOG_FILE_PAT.match(csvbasename)
    if m_log:
        csvbasename = m_log.group("base")
    csvpath = None
    csvout = None
    csvwriter = None
    hello = None
    threads = None
    founds: dict[str, set[str] | None] = {}
    for entry in entries:
        if csvwriter is None and entry.message != "hello":
            raise ValueError("expected first entry to be hello", dict(entry=entry))
        if entry.message == "hello":
            if hello is not None:
                if hello.module != entry.module:
                    raise ValueError(
                        "hello mismatch", dict(previous=hello, current=entry)
                    )
                csvout.close()
            hello = entry
            threads = {entry.thread_id: "<HELLO>"}
            csvpath = logpath.parent / (
                csvbasename
                + "."
                + hello.timestamp_dt.strftime("%Y-%m-%d-%H%M%S")
                + ".csv"
            )
            csvout = csvpath.open("wt", encoding="utf-8", newline="")
            print("| Writing to:", csvpath)
            csvwriter = csv.writer(csvout)
            csvwriter.writerow(
                [
                    "type",
                    # "linenum since hello",
                    # "seconds since hello",
                    "module",
                    "function",
                    "thread_id",
                    "file",
                    "level",
                    "message",
                ]
            )

        if entry.thread_id not in threads:
            threads[entry.thread_id] = f"<{len(threads)}>"

        entry.message_without_parameters

        if "found" in entry.labels:
            for n in entry.parameters.keys():
                founds.setdefault(n)

        for foundname, foundset in founds.items():
            data = entry.parameters.get(foundname)
            if data is not None:
                if foundset is None:
                    foundset = founds[foundname] = set()
                try:
                    data = float(data)
                    data = int(data)
                except ValueError as e:
                    pass
                foundset.add(data)
            else:
                if foundset is not None:
                    for data in sorted(foundset):
                        csvwriter.writerow(
                            [
                                f"found {foundname}",
                                # entry.linenum - hello.linenum,
                                # round_up_duration(entry.timestamp_dt - hello.timestamp_dt),
                                "#",  # entry.module,
                                "#",  # entry.function,
                                "#",  # threads[entry.thread_id],
                                "#",  # pathlib.Path(entry.file).name,
                                "#",  # entry.level,
                                str(data),
                            ]
                        )
                    foundset = founds[foundname] = None

        csvwriter.writerow(
            [
                "entry",
                # entry.linenum - hello.linenum,
                # round_up_duration(entry.timestamp_dt - hello.timestamp_dt),
                entry.module,
                entry.function,
                threads[entry.thread_id],
                pathlib.Path(entry.file).name,
                entry.level,
                entry.message_without_parameters,
            ]
        )

        data = entry.parameters.get("json")
        if data is not None:
            csvwriter.writerow(
                [
                    "json",
                    # entry.linenum - hello.linenum,
                    # round_up_duration(entry.timestamp_dt - hello.timestamp_dt),
                    "#",  # entry.module,
                    "#",  # entry.function,
                    "#",  # threads[entry.thread_id],
                    "#",  # pathlib.Path(entry.file).name,
                    "#",  # entry.level,
                    json.dumps(data, indent=4, sort_keys=True),
                ]
            )

    if csvout is not None:
        csvout.close()


def round_up_duration(dur: datetime.timedelta) -> int:
    secs = dur.total_seconds()
    for thresh in [1, 10, 60, 120, 300, 600, 1800, 3600]:
        if secs < thresh:
            return thresh
    return int("1" + "0" * len(str(round(secs))))


def default_hostscan_log_dir() -> pathlib.Path:
    # Use default HostScan log location for the current platform,
    # as documented under "Posture Modules' Log Files and Locations",
    # in <https://www.cisco.com/c/en/us/td/docs/security/vpn_client/anyconnect/anyconnect40/administration/guide/b_AnyConnect_Administrator_Guide_4-0/configure-posture.html>
    if platform.system() == "Windows":
        return (
            pathlib.Path(os.environ["LOCALAPPDATA"])
            / "Cisco"
            / "Cisco HostScan"
            / "log"
        )
    else:
        return pathlib.Path(os.environ("HOME")) / ".cisco" / "hostscan" / "log"


def main():
    if len(sys.argv) > 1:
        args = sys.argv[1:]
    else:
        args = [default_hostscan_log_dir()]

    logs = []
    for arg in args:
        if arg == "++DEFAULT++":
            arg = default_hostscan_log_dir()
        arg = pathlib.Path(arg)
        if arg.is_file():
            # Specified a file directly, so do not check name
            logs.append(arg)
        elif arg.is_dir():
            # Specified a directory, so only check for log files and rolled over log files
            for child in arg.iterdir():
                if child.is_file() and LOG_FILE_PAT.match(child.name):
                    logs.append(child)

    for logpath in logs:
        print("Reading:", logpath)
        try:
            analyze_hostscan_log(logpath)
        except ValueError as e:
            print("!!", e)
            sys.exit(1)


if __name__ == "__main__":
    main()
