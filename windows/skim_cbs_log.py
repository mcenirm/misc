from __future__ import annotations

import abc
import dataclasses
import datetime
import pathlib
import re
import sys
import typing

from icecream import ic

YYYY_MM_DD_HH_MM_SS = r"\d\d\d\d-\d\d-\d\d \d\d:\d\d:\d\d"
YYYY_MM_DD_HH_MM_SS_SSS = YYYY_MM_DD_HH_MM_SS + r"\.\d\d\d"


class Message:
    _reg: dict[str, type[Message]] = {}

    def __init_subclass__(cls) -> None:
        if not cls.__name__.startswith("_"):
            Message._reg[cls.__qualname__] = cls

    @classmethod
    def from_line(cls, lineno: int, line: str) -> Message:
        mtch = re.compile(
            rf"(?P<dt>{YYYY_MM_DD_HH_MM_SS})"
            + r", "
            + r"(?P<lvl>Info|Error) ?"
            + r"                 "
            + r"(?P<src>CBS|CSI)"
            + r"    "
            + r"(?P<msg>.*)"
        ).fullmatch(line)
        if not mtch:
            raise ValueError("bad line", lineno, line)
        dt, lvl, src, msg = mtch.groups()
        mtch = re.compile(r"(?P<typ>\w+)" + r": " + r"(?P<submsg>.*)").fullmatch(msg)
        if mtch:
            typ, submsg = mtch.groups()
            if typ in Message._reg:
                return Message._reg[typ].from_submsg(
                    lineno=lineno,
                    line=line,
                    dt=dt,
                    lvl=lvl,
                    src=src,
                    msg=msg,
                    submsg=submsg,
                )
            else:
                raise KeyError(
                    "bad type in msg",
                    dict(
                        lineno=lineno,
                        line=line,
                        dt=dt,
                        lvl=lvl,
                        src=src,
                        msg=msg,
                        typ=typ,
                        submsg=submsg,
                    ),
                )
        else:
            return cls(
                lineno=lineno,
                line=line,
                dt=dt,
                lvl=lvl,
                src=src,
                msg=msg,
            )

    @classmethod
    @abc.abstractmethod
    def from_submsg(
        cls, lineno: int, line: str, dt: str, lvl: str, src: str, msg: str, submsg: str
    ) -> Message:
        raise NotImplementedError(dict(cls=cls))

    def __init__(
        self, lineno: int, line: str, dt: str, lvl: str, src: str, msg: str
    ) -> None:
        self.lineno = lineno
        self.line = line
        self.dt = dt
        self.lvl = lvl
        self.src = src
        self.msg = msg


class _SubMessage(Message):
    @classmethod
    def from_submsg(
        cls, lineno: int, line: str, dt: str, lvl: str, src: str, msg: str, submsg: str
    ) -> _SubMessage:
        return cls(
            lineno=lineno,
            line=line,
            dt=dt,
            lvl=lvl,
            src=src,
            msg=msg,
            submsg=submsg,
        )

    def __init__(
        self, lineno: int, line: str, dt: str, lvl: str, src: str, msg: str, submsg: str
    ) -> None:
        super().__init__(lineno, line, dt, lvl, src, msg)
        self.submsg = submsg


class TI(_SubMessage): ...


class Lock(_SubMessage): ...


def _c_(*args: str, sep="") -> str:
    return str(sep).join(map(str, args))


def _g_(*args: str, name: str | None = None) -> str:
    return r"(" + ("" if name is None else rf"?P<{name}>") + _c_(*args) + r")"


def _a_(*args: str, name: str | None = None) -> str:
    return _g_(_c_(*args, sep=r"|"), name=name)


LOG_LINE1_PAT = re.compile(
    _c_(
        _g_(YYYY_MM_DD_HH_MM_SS, name="dt"),
        r", ",
        _a_(r"Info", r"Error", name="lvl"),
        r" ?                 ",
        _a_(r"CBS", r"CSI", name="src"),
        r"    ",
        _g_(r"\S.*", name="msg"),
    )
)
PACKAGE_PAT = re.compile(r"[^~ '\\]+~[0-9a-f]+~amd64~([a-z]+-[A-Z]+)?~\d[0-9.]+\d")


INFO = "Info"
ERROR = "Error"
CBS = "CBS"
CBS_TI = "TI: "
CBS_TI_INITIALIZING_TRUSTED_INSTALLER = "--- Initializing Trusted Installer ---"
CBS_TI_LAST_BOOT_TIME = "Last boot time:"
CBS_STARTING_TRUSTED_INSTALLER_INITIALIZATION = (
    "Starting TrustedInstaller initialization."
)
CBS_LOCK = "Lock: "
CBS_LOCK_NEW_LOCK_ADDED = re.compile(
    r"New lock added: (?P<cls>\w+), level: (?P<level>\d+), total lock:(?P<total_lock>\d+)"
)
CBS_ENDING_TRUSTED_INSTALLER_INITIALIZATION = "Ending TrustedInstaller initialization."
CBS_STARTING_THE_TRUSTED_INSTALLER_MAIN_LOOP = (
    "Starting the TrustedInstaller main loop."
)
CBS_TRUSTED_INSTALLER_SERVICE_STARTS_SUCCESSFULLY = (
    "TrustedInstaller service starts successfully."
)
CBS_NO_STARTUP_PROCESSING_REQUIRED_TRUSTED_INSTALLER_SERVICE_WAS_NOT_SET_AS_AUTOSTART = (
    "No startup processing required, TrustedInstaller service was not set as autostart"
)
CBS_STARTUP_PROCESSING_THREAD_TERMINATED_NORMALLY = (
    "Startup processing thread terminated normally"
)
CBS_TI_STARTUP_PROCESSING_COMPLETES_RELEASE_STARTUP_PROCESSING_LOCK = (
    "Startup Processing completes, release startup processing lock."
)
CBS_STARTING_TIWORKER_INITIALIZATION = "Starting TiWorker initialization."
CBS_ENDING_TIWORKER_INITIALIZATION = "Ending TiWorker initialization."
CBS_STARTING_THE_TIWORKER_MAIN_LOOP = "Starting the TiWorker main loop."
CBS_TIWORKER_STARTS_SUCCESSFULLY = "TiWorker starts successfully."
CBS_UNIVERSAL_TIME_IS = "Universal Time is:"
CBS_LOADED_SERVICING_STACK_WITH_CORE = re.compile(
    r"Loaded Servicing Stack (?P<stack_version>v\d[0-9.]+\d) with Core: (?P<cbscore_dll>[-A-Z:\\a-z0-9_.]+)"
)


@dataclasses.dataclass
class LogEntry:
    lineno: int
    line: str
    extralines: list[str]
    dt: datetime.datetime
    dtgap: datetime.timedelta
    lvl: str
    src: str
    msg: str
    pkgs: set[str]

    def debug(self) -> list[str]:
        return [
            "  ".join(
                map(
                    str,
                    [
                        str(self.lineno).rjust(7),
                        self.lvl,
                        self.src,
                        f"{self.dt} ({self.dtgap if self.dtgap < datetime.timedelta.max else 'n/a'})",
                    ],
                )
            )
        ] + [": " + s for s in [self.msg] + self.extralines]

    def print(self, print=print) -> None:
        for dbg in self.debug():
            print(dbg)


def coalesce_entries(
    lines: typing.Iterable[str],
) -> typing.Generator[LogEntry, None, None]:
    nextentry: LogEntry | None = None
    prevdt: datetime.datetime | None = None
    for lineno, line in enumerate(lines, 1):
        mtch = LOG_LINE1_PAT.fullmatch(line)
        if mtch:
            if isinstance(nextentry, LogEntry):
                yield nextentry
                nextentry = None
            dt, lvl, src, msg = mtch.groups()
            dt = datetime.datetime.strptime(dt, r"%Y-%m-%d %H:%M:%S")
            if isinstance(prevdt, datetime.datetime):
                dtgap = dt - prevdt
            else:
                dtgap = datetime.timedelta.max
            prevdt = dt
            nextentry = LogEntry(
                lineno=lineno,
                line=line,
                extralines=[],
                dt=dt,
                dtgap=dtgap,
                lvl=lvl,
                src=src,
                msg=msg,
                pkgs=set(),
            )
        else:
            if isinstance(nextentry, LogEntry):
                nextentry.extralines.append(line)
            else:
                raise AssertionError("bad nextentry", nextentry, lineno, line)
        if "~" in line:
            for mtch in PACKAGE_PAT.finditer(line):
                nextentry.pkgs.add(mtch.group())
    if isinstance(nextentry, LogEntry):
        yield nextentry


def should_ignore(entry: LogEntry) -> bool:
    if should_ignore_cbs(entry):
        return True
    return False


def should_ignore_cbs(entry: LogEntry) -> bool:
    if entry.msg in {
        CBS_STARTING_TRUSTED_INSTALLER_INITIALIZATION,
        CBS_ENDING_TRUSTED_INSTALLER_INITIALIZATION,
        CBS_STARTING_THE_TRUSTED_INSTALLER_MAIN_LOOP,
        CBS_TRUSTED_INSTALLER_SERVICE_STARTS_SUCCESSFULLY,
        CBS_NO_STARTUP_PROCESSING_REQUIRED_TRUSTED_INSTALLER_SERVICE_WAS_NOT_SET_AS_AUTOSTART,
        CBS_STARTUP_PROCESSING_THREAD_TERMINATED_NORMALLY,
        CBS_STARTING_TIWORKER_INITIALIZATION,
        CBS_ENDING_TIWORKER_INITIALIZATION,
        CBS_STARTING_THE_TIWORKER_MAIN_LOOP,
        CBS_TIWORKER_STARTS_SUCCESSFULLY,
    }:
        return True
    if entry.msg.startswith(CBS_UNIVERSAL_TIME_IS):
        return True
    if CBS_LOADED_SERVICING_STACK_WITH_CORE.fullmatch(entry.msg):
        return True
    if should_ignore_cbs_ti(entry):
        return True
    if should_ignore_cbs_lock(entry):
        return True
    return False


def should_ignore_cbs_ti(entry: LogEntry) -> bool:
    if entry.msg.startswith(CBS_TI):
        rest = entry.msg.removeprefix(CBS_TI)
        if rest in {
            CBS_TI_INITIALIZING_TRUSTED_INSTALLER,
            CBS_TI_STARTUP_PROCESSING_COMPLETES_RELEASE_STARTUP_PROCESSING_LOCK,
        }:
            return True
        if rest.startswith(CBS_TI_LAST_BOOT_TIME):
            return True
    return False


def should_ignore_cbs_lock(entry: LogEntry) -> bool:
    if entry.msg.startswith(CBS_LOCK):
        rest = entry.msg.removeprefix(CBS_LOCK)
        if CBS_LOCK_NEW_LOCK_ADDED.fullmatch(rest):
            return True
    return False


def main():
    logfile = pathlib.Path(sys.argv[1])
    info_count = 0
    error_count = 0
    package_name_to_entry: dict[str, list[LogEntry]] = {}
    errors: list[LogEntry] = []
    entries = list(
        coalesce_entries(logfile.read_text(encoding="utf-8-sig").splitlines())
    )
    for entry in entries:
        for pkg in entry.pkgs:
            if pkg not in package_name_to_entry:
                package_name_to_entry[pkg] = []
            package_name_to_entry[pkg].append(entry)
        if entry.lvl == INFO:
            info_count += 1
        elif entry.lvl == ERROR:
            error_count += 1
            errors.append(entry)
        else:
            raise ValueError("level", entry.lvl, entry)
    print("info:  ", info_count)
    print("error: ", error_count)
    for e in errors:
        print()
        e.print()
    for e in entries:
        if should_ignore(e):
            continue
        else:
            print()
            e.print()
            break
    print()
    print("count of log entries: ", len(entries))
    print("size of time range:   ", entries[-1].dt - entries[0].dt)


if __name__ == "__main__":
    sys.exit(main())
