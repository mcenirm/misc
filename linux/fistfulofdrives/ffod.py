from __future__ import annotations

import collections.abc
import copy
import dataclasses
import difflib
import functools
import json
import keyword
import pathlib
import shlex
import sqlite3
import subprocess
import sys
import tomllib
import types
import typing
import uuid


def main(cfgfile: pathlib.Path = None):
    if "--regenerate-block-device-class-from-lsblk" in sys.argv:
        _regenerate_block_device_class_from_lsblk()
        return

    cfg = Config()
    if cfgfile is not None:
        cfg.toml_file = cfgfile
    cfg.load()

    db = Database(dbfile=cfg.db_file)

    usbdevs = get_usb_devices()
    all_vols: dict[int, BlockDevice] = {}
    for usbdev in usbdevs:
        usbid = db.note_usb_device(usbdev)
        candidates = list_block_devices(devices=[usbdev.path])

        # Only look at volumes
        vols = [bd for bd in candidates if is_volume(bd)]

        # Only look at volumes that are relevant to us,
        # and that do not have the "ignore" marker file
        vols = [bd for bd in vols if not ignore_volume(bd, cfg.ignore_volume_filename)]

        for vol in vols:
            volid = db.note_volume(vol, usbid=usbid)
            if volid in all_vols:
                raise IndexError("volume ID collision", volid, all_vols[volid], vol)
            all_vols[volid] = vol

    ready_results = are_volumes_ready(all_vols.values(), cfg.mount_tree)
    show_actions_for_volume_ready(ready_results)

    raise NotImplementedError("what to do after seeing if volumes are ready?")


IGNORE_PARTTYPE_UUIDS = {
    uuid.UUID("c12a7328-f81f-11d2-ba4b-00a0c93ec93b"): (
        "EFI System Partition",
        "ESP",
    ),
    uuid.UUID("e3c9e316-0b5c-4db8-817d-f92df00215ae"): (
        "Microsoft Reserved Partition",
        "MSR",
    ),
}
IGNORE_FSTYPES = {
    "ntfs": "NTFS",
}


METADATA_HOLDER = "holder"
METADATA_KEY = "key"
METADATA_DESC = "desc"
LSBLK_KNOWN_PLURALS = {
    "FSROOTS",
    "MOUNTPOINTS",
}
LSBLK_KNOWN_UNSTABLES = {
    "DISK_SEQ",
    "FSAVAIL",
    "FSROOTS",
    "FSSIZE",
    "FSUSE_PCT",
    "FSUSED",
    "HCTL",
    "KNAME",
    "MAJ_MIN",
    "MIN",
    "MOUNTPOINT",
    "MOUNTPOINTS",
    "NAME",
    "PATH",
}


def _regenerate_block_device_class_from_lsblk():
    typemap = {
        "string": str.__name__,
        "[string]": list.__name__ + "[" + str.__name__ + "]",
        "integer": int.__name__,
        "boolean": bool.__name__,
        "size": DataSize.__name__,
    }
    bytesdescsuffix = ", use <number> if --bytes is given"
    bytestypenames = {"number", "string"}
    sizetypenames = {"size"}

    data = lsblk("--list-columns")
    cols: list[dict[str, str]] = data["lsblk-columns"]

    print("@dataclasses.dataclass(repr=False)")
    print(
        "class BlockDevice("
        + ",".join(
            [cls.__name__ for cls in [_DataclassConciseRepr, _DataclassTypeFixer]]
        )
        + "):"
    )
    for col in cols:
        holder = col[METADATA_HOLDER]
        typenames = set(col["type"].removeprefix("<").removesuffix(">").split("|"))
        desc = col["description"]

        if desc.endswith(bytesdescsuffix) and typenames == bytestypenames:
            typenames = sizetypenames
            desc = desc.removesuffix(bytesdescsuffix)

        name = holder.lower().replace("-", "_").replace(":", "_").replace("%", "_pct")
        assert not keyword.iskeyword(name), (name, holder, desc)
        assert name.isidentifier(), (name, holder, desc)

        # TODO is this assertion necessary?
        assert len(typenames) == 1, (holder, typenames, desc)
        if holder in LSBLK_KNOWN_PLURALS:
            sortedsimpletypenames = sorted(typenames)
            typenames = []
            for n in sortedsimpletypenames:
                typenames.append(n)
                typenames.append("[" + n + "]")
        typelistasstr = "|".join([typemap[n] for n in typenames])

        print(
            "    "
            + name
            + ":"
            + typelistasstr
            + "=_f("
            + repr(holder)
            + ","
            + repr(desc)
            + ")"
        )


@dataclasses.dataclass
class _DataclassTypeFixer:
    def __post_init__(self) -> None:
        hints = typing.get_type_hints(self.__class__)
        for fld in dataclasses.fields(self):
            curval = getattr(self, fld.name)
            if curval is None:
                continue
            expected_type = hints[fld.name]
            newval = coerce_value_to_type(curval, expected_type)
            if newval is not curval:
                object.__setattr__(self, fld.name, newval)


def coerce_value_to_type(value: object, targettype: type) -> object:
    actual_type = type(value)
    if actual_type == targettype:
        return value
    else:
        if isinstance(targettype, types.UnionType):
            also_try_str = False
            for subtype in targettype.__args__:
                if subtype is str:
                    also_try_str = True
                else:
                    try:
                        return coerce_value_to_type(value, subtype)
                    except TypeError as te:
                        pass
            if also_try_str:
                return str(value)
        return targettype(value)


@dataclasses.dataclass
class _DataclassConciseRepr:

    def __repr__(self):
        return (
            self.__class__.__name__
            + "("
            + ", ".join(
                [
                    f.name + "=" + repr(getattr(self, f.name))
                    for f in sorted(dataclasses.fields(self), key=lambda f: f.name)
                    if getattr(self, f.name) != f.default
                ]
            )
            + ")"
        )


def _f(holder: str, desc: str) -> dataclasses.Field:
    return dataclasses.field(
        default=None,
        metadata={
            METADATA_HOLDER: holder,
            METADATA_KEY: holder.lower(),
            METADATA_DESC: desc,
        },
    )


@dataclasses.dataclass(repr=False)
class BlockDevice(_DataclassConciseRepr, _DataclassTypeFixer):
    alignment: int = _f("ALIGNMENT", "alignment offset")
    id_link: str = _f("ID-LINK", "the shortest udev /dev/disk/by-id link name")
    id: str = _f("ID", "udev ID (based on ID-LINK)")
    disc_aln: int = _f("DISC-ALN", "discard alignment offset")
    dax: bool = _f("DAX", "dax-capable device")
    disc_gran: DataSize = _f("DISC-GRAN", "discard granularity")
    disk_seq: int = _f("DISK-SEQ", "disk sequence number")
    disc_max: DataSize = _f("DISC-MAX", "discard max bytes")
    disc_zero: bool = _f("DISC-ZERO", "discard zeroes data")
    fsavail: DataSize = _f(
        "FSAVAIL", "filesystem size available for unprivileged users"
    )
    fsroots: str | list[str] = _f("FSROOTS", "mounted filesystem roots")
    fssize: DataSize = _f("FSSIZE", "filesystem size")
    fstype: str = _f("FSTYPE", "filesystem type")
    fsused: DataSize = _f("FSUSED", "filesystem size used")
    fsuse_pct: str = _f("FSUSE%", "filesystem use percentage")
    fsver: str = _f("FSVER", "filesystem version")
    group: str = _f("GROUP", "group name")
    hctl: str = _f("HCTL", "Host:Channel:Target:Lun for SCSI")
    hotplug: bool = _f("HOTPLUG", "removable or hotplug device (usb, pcmcia, ...)")
    kname: str = _f("KNAME", "internal kernel device name")
    label: str = _f("LABEL", "filesystem LABEL")
    log_sec: int = _f("LOG-SEC", "logical sector size")
    maj_min: str = _f("MAJ:MIN", "major:minor device number")
    maj: str = _f("MAJ", "major device number")
    min: str = _f("MIN", "minor device number")
    min_io: int = _f("MIN-IO", "minimum I/O size")
    mode: str = _f("MODE", "device node permissions")
    model: str = _f("MODEL", "device identifier")
    mq: str = _f("MQ", "device queues")
    name: str = _f("NAME", "device name")
    opt_io: int = _f("OPT-IO", "optimal I/O size")
    owner: str = _f("OWNER", "user name")
    partflags: str = _f("PARTFLAGS", "partition flags")
    partlabel: str = _f("PARTLABEL", "partition LABEL")
    partn: int = _f("PARTN", "partition number as read from the partition table")
    parttype: str = _f("PARTTYPE", "partition type code or UUID")
    parttypename: str = _f("PARTTYPENAME", "partition type name")
    partuuid: str = _f("PARTUUID", "partition UUID")
    path: str = _f("PATH", "path to the device node")
    phy_sec: int = _f("PHY-SEC", "physical sector size")
    pkname: str = _f("PKNAME", "internal parent kernel device name")
    pttype: str = _f("PTTYPE", "partition table type")
    ptuuid: str = _f("PTUUID", "partition table identifier (usually UUID)")
    ra: int = _f("RA", "read-ahead of the device")
    rand: bool = _f("RAND", "adds randomness")
    rev: str = _f("REV", "device revision")
    rm: bool = _f("RM", "removable device")
    ro: bool = _f("RO", "read-only device")
    rota: bool = _f("ROTA", "rotational device")
    rq_size: int = _f("RQ-SIZE", "request queue size")
    sched: str = _f("SCHED", "I/O scheduler name")
    serial: str = _f("SERIAL", "disk serial number")
    size: DataSize = _f("SIZE", "size of the device")
    start: int = _f("START", "partition start offset (in 512-byte sectors)")
    state: str = _f("STATE", "state of the device")
    subsystems: str = _f("SUBSYSTEMS", "de-duplicated chain of subsystems")
    mountpoint: str = _f("MOUNTPOINT", "where the device is mounted")
    mountpoints: str | list[str] = _f(
        "MOUNTPOINTS", "all locations where device is mounted"
    )
    tran: str = _f("TRAN", "device transport type")
    type: str = _f("TYPE", "device type")
    uuid: str = _f("UUID", "filesystem UUID")
    vendor: str = _f("VENDOR", "device vendor")
    wsame: DataSize = _f("WSAME", "write same max bytes")
    wwn: str = _f("WWN", "unique storage identifier")
    zoned: str = _f("ZONED", "zone model")
    zone_sz: DataSize = _f("ZONE-SZ", "zone size")
    zone_wgran: DataSize = _f("ZONE-WGRAN", "zone write granularity")
    zone_app: DataSize = _f("ZONE-APP", "zone append max bytes")
    zone_nr: int = _f("ZONE-NR", "number of zones")
    zone_omax: int = _f("ZONE-OMAX", "maximum number of open zones")
    zone_amax: int = _f("ZONE-AMAX", "maximum number of active zones")


BLOCKDEVICE_NAME_TO_KEY: dict[str, str] = {
    f.name: f.metadata[METADATA_KEY] for f in dataclasses.fields(BlockDevice)
}
BLOCKDEVICE_KEY_TO_NAME: dict[str, str] = {
    f.metadata[METADATA_KEY]: f.name for f in dataclasses.fields(BlockDevice)
}

FFOD_DB_NAME_USB = "usb"
FFOD_DB_NAME_VOL = "vol"
FFOD_DB_NAME_FIRSTSEENUTC = "firstseenutc"
FFOD_DB_NAME_VENDOR = "vendor"
FFOD_DB_NAME_MODEL = "model"
FFOD_DB_NAME_SERIAL = "serial"
FFOD_DB_NAME_SIZE = "size"
FFOD_DB_NAME_LABEL = "label"
FFOD_DB_NAME_UUID = "uuid"

FILTER_USB, FILTER_NOT_USB = (
    f'{BLOCKDEVICE_NAME_TO_KEY["tran"]} {op} "usb"' for op in ["eq", "ne"]
)
USB_DEVICES_OUTPUT_KEYS = [
    BLOCKDEVICE_NAME_TO_KEY[n]
    for n in [
        "tran",
        "path",
        FFOD_DB_NAME_VENDOR,
        FFOD_DB_NAME_MODEL,
        FFOD_DB_NAME_VENDOR,
        FFOD_DB_NAME_SERIAL,
        FFOD_DB_NAME_SIZE,
    ]
]

IEC_MULTIPLIERS = {
    "K": 1024,
    "M": 1024**2,
    "G": 1024**3,
    "T": 1024**4,
    "P": 1024**5,
}


class DataSize:
    def __init__(self, val: str | int):
        self.origval = val
        if isinstance(val, int):
            self.sizebytes = val
            self.units = "B"
            self.size = val
        elif isinstance(val, str):
            val = val.strip()
            for i, ch in enumerate(val):
                if not (ch == "." or ch.isnumeric()):
                    break
            self.size = float(val[:i])
            if int(self.size) == self.size:
                self.size = int(self.size)
            self.units = val[i:].strip().upper()
            self.sizebytes = int(self.size * IEC_MULTIPLIERS[self.units])
        else:
            raise ValueError('expected string ("123M") or integer (size in bytes)', val)

    def __str__(self):
        return str(self.origval)

    def __repr__(self):
        return self.__class__.__name__ + "(" + repr(self.origval) + ")"


@dataclasses.dataclass(frozen=True, kw_only=True)
class VolumeReadyCheckResult:
    vol: BlockDevice
    expected_mountpoint: pathlib.Path
    actual_mountpoint: pathlib.Path | None
    needs_remount: bool
    bad_mountpoint: bool
    missing_mountpoint: bool
    pending_mount: bool

    @property
    def is_ready(self) -> bool:
        return not (
            self.needs_remount
            or self.bad_mountpoint
            or self.missing_mountpoint
            or self.pending_mount
        )

    def __bool__(self) -> bool:
        return self.is_ready


def is_volume_ready(
    vol: BlockDevice, mount_tree: pathlib.Path
) -> VolumeReadyCheckResult:
    expected_mountpoint = mount_tree / f"{vol.label},{vol.uuid}"
    actual_mountpoint = pathlib.Path(vol.mountpoint) if vol.mountpoint else None
    needs_remount = False
    bad_mountpoint = False
    missing_mountpoint = False
    pending_mount = False

    if not expected_mountpoint.is_dir(follow_symlinks=False):
        if expected_mountpoint.exists():
            bad_mountpoint = True
        else:
            missing_mountpoint = True
    if actual_mountpoint and actual_mountpoint != expected_mountpoint:
        needs_remount = True
    elif not actual_mountpoint:
        pending_mount = True

    return VolumeReadyCheckResult(
        vol=vol,
        expected_mountpoint=expected_mountpoint,
        actual_mountpoint=actual_mountpoint,
        needs_remount=needs_remount,
        bad_mountpoint=bad_mountpoint,
        missing_mountpoint=missing_mountpoint,
        pending_mount=pending_mount,
    )


def are_volumes_ready(
    vols: list[BlockDevice], mount_tree: pathlib.Path
) -> list[VolumeReadyCheckResult]:
    return [is_volume_ready(vol, mount_tree) for vol in vols]


def show_actions_for_volume_ready(
    results: list[VolumeReadyCheckResult], print=print
) -> None:
    dump_table(
        [
            [vol.name, vol.fstype, vol.mountpoint]
            for vol in [res.vol for res in results]
        ],
        print=print,
    )

    vols_with_bad_mountpoint = [res for res in results if res.bad_mountpoint]
    if vols_with_bad_mountpoint:
        print("!!!! FIX MOUNTPOINT (should be directory) !!!!")
        dump_table(
            [
                [res.vol.name, res.expected_mountpoint]
                for res in vols_with_bad_mountpoint
            ],
            print=print,
        )
    vols_that_need_remount = [res for res in results if res.needs_remount]
    if vols_that_need_remount:
        print("!!!! UNMOUNT AND REMOUNT !!!!")
        dump_table(
            [
                [res.vol.name, res.vol.mountpoint, res.expected_mountpoint]
                for res in vols_that_need_remount
            ],
            print=print,
        )
    vols_with_missing_mountpoint = [res for res in results if res.missing_mountpoint]
    if vols_with_missing_mountpoint:
        print("# need mountpoint")
        dump_table(
            [
                ["#", res.vol.name, res.expected_mountpoint]
                for res in vols_with_missing_mountpoint
            ],
            print=print,
        )
        for vol, expmt in vols_with_missing_mountpoint:
            print(f"sudo mkdir -v {shlex.quote(str(expmt))}    #  {vol.name}")
        print()
    vols_that_need_mount = [res for res in results if res.pending_mount]
    if vols_that_need_mount:
        print("# need mount")
        dump_table(
            [
                ["#", res.vol.name, res.expected_mountpoint]
                for res in vols_that_need_mount
            ],
            print=print,
        )
        for res in vols_that_need_mount:
            print(
                f"sudo mount -v UUID={res.vol.uuid} {shlex.quote(str(res.expected_mountpoint))}"
            )
        print()


def get_usb_devices(
    filter=FILTER_USB,
    outputkeys=USB_DEVICES_OUTPUT_KEYS,
) -> list[BlockDevice]:
    return list_block_devices(outputkeys=outputkeys, filter=filter)


def is_volume(bd: BlockDevice) -> bool:
    if bd.fstype is not None:
        return True
    return False


def ignore_volume(bd: BlockDevice, ignore_volume_filename: str) -> bool:
    try:
        if uuid.UUID(bd.parttype) in IGNORE_PARTTYPE_UUIDS:
            return True
    except ValueError:
        pass

    if bd.fstype in IGNORE_FSTYPES:
        return True

    try:
        if (
            bd.mountpoint
            and (pathlib.Path(bd.mountpoint) / ignore_volume_filename).exists()
        ):
            return True
    except PermissionError:
        pass

    return False


LSBLK = "/usr/bin/lsblk"


def list_block_devices(
    devices: list[str] = None,
    outputkeys: list[str] = "*",
    filter: str = None,
    inbytes: bool = True,
) -> list[BlockDevice]:
    args = ["--list"]

    if inbytes:
        args.append("--bytes")

    if filter is not None:
        args.append("--filter")
        args.append(filter)

    if isinstance(outputkeys, str):
        outputkeys = [outputkeys]
    if isinstance(outputkeys, list):
        if "*" in outputkeys:
            args.append("--output-all")
        else:
            args.append("--output")
            args.append(",".join(outputkeys))
    elif outputkeys is not None:
        raise ValueError("unexpected outputkeys", outputkeys)

    if devices is not None:
        args.extend(devices)

    data = lsblk(*args)
    blockdevices: list[BlockDevice] = []
    for bddata in data["blockdevices"]:
        bd = BlockDevice(**{BLOCKDEVICE_KEY_TO_NAME[k]: v for k, v in bddata.items()})
        blockdevices.append(bd)
    return blockdevices


def lsblk_as_text(*args: str, _exe=LSBLK) -> str:
    runargs = [_exe, *args]
    setx(runargs)
    return subprocess.check_output(runargs, text=True)


def lsblk(*args: str, _exe=LSBLK) -> object:
    return json.loads(lsblk_as_text("--json", *args, _exe=_exe))


def setx(args: list[str], print=functools.partial(print, file=sys.stderr)):
    print("++", *[shlex.quote(a) for a in args])


class Cmd:
    def __init__(self, exe: pathlib.Path):
        self.exe = exe

    def _runargs(self, cmdopts: dict[str, str], cmdargs: list[str]) -> list[str]:
        runargs = [self.exe]
        for optname, optarg in cmdopts.items():
            runargs.append(optname)
            if optarg is not None:
                runargs.append(optarg)
        runargs.extend(cmdargs)
        return list(map(shlex.quote, runargs))

    def run_json(
        self,
        cmdopts: dict[str, str] = {},
        cmdargs: list[str] = [],
        runkwargs: dict[str, typing.Any] = {},
    ) -> typing.Generator[object, None, None]:
        runkwargs = dict(runkwargs)
        runkwargs.pop("text", None)
        text = subprocess.check_output(
            self._runargs(cmdopts=cmdopts, cmdargs=cmdargs),
            text=True,
            **runkwargs,
        )
        while text:
            try:
                o = json.loads(text)
            except json.JSONDecodeError as e:
                if "extra" in e.msg.lower():
                    text = text[e.pos :]
                else:
                    raise
            yield o

    def run_lines(
        self,
        cmdopts: dict[str, str] = {},
        cmdargs: list[str] = [],
        runkwargs: dict[str, typing.Any] = {},
    ) -> typing.Generator[str, None, None]:
        runkwargs = dict(runkwargs)
        runkwargs.pop("text", None)
        text = subprocess.check_output(
            self._runargs(cmdopts=cmdopts, cmdargs=cmdargs),
            text=True,
            **runkwargs,
        )
        yield from text.splitlines()


class JsonAsOutputArgMixin:
    def run_json(
        self,
        cmdopts: dict[str, str],
        cmdargs: list[str],
        runkwargs: dict[str, typing.Any],
    ) -> typing.Generator[object, None, None]:
        cmdopts = dict(cmdopts)
        cmdopts["--output"] = "json"
        super().run_json(cmdopts=cmdopts, cmdargs=cmdargs, runkwargs=runkwargs)


class JsonAsFlagMixin:
    def run_json(
        self,
        cmdopts: dict[str, str],
        cmdargs: list[str],
        runkwargs: dict[str, typing.Any],
    ) -> typing.Generator[object, None, None]:
        cmdopts = dict(cmdopts)
        cmdopts["--output"] = "json"
        super().run_json(cmdopts=cmdopts, cmdargs=cmdargs, runkwargs=runkwargs)


class Lsblk(Cmd, JsonAsOutputArgMixin):
    def __init__(self, exe="/usr/bin/lsblk"):
        super().__init__(exe)


class Blkid(Cmd):
    def __init__(self, exe="/usr/sbin/blkid"):
        super().__init__(exe)

    def devices(self) -> list[str]:
        return list(self.run_lines({"--output": "device"}))


def dump_table(table: list[list[str]], print=print):
    table = [[str(cell) for cell in row] for row in table]
    widths = [0] * max([len(row) for row in table])
    for row in table:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    for row in table:
        print(*[c.ljust(w) for c, w in zip(row, widths)])


@dataclasses.dataclass
class Config:
    app_name: str = "ffod"

    mount_tree: pathlib.Path = pathlib.Path("/media/ffod")
    state_tree: pathlib.Path = pathlib.Path(__file__).parent
    index_tree: pathlib.Path = None
    copy_tree: pathlib.Path = None

    toml_suffix: str = ".toml"
    ignore_volume_file_prefix: str = "."
    ignore_volume_file_suffix: str = ".ignore.volume.txt"
    db_suffix: str = ".db"

    _toml_file: pathlib.Path = None
    _ignore_volume_filename: str = None
    _db_file: pathlib.Path = None

    @property
    def toml_file(self) -> pathlib.Path:
        return self._toml_file or (
            self.state_tree / f"{self.app_name}{self.toml_suffix}"
        )

    @toml_file.setter
    def toml_file(self, value):
        self._toml_file = value

    @property
    def ignore_volume_filename(self) -> str:
        return (
            self._ignore_volume_filename
            or f"{self.ignore_volume_file_prefix}{self.app_name}{self.ignore_volume_file_suffix}"
        )

    @ignore_volume_filename.setter
    def ignore_volume_filename(self, value):
        self._ignore_volume_filename = value

    @property
    def db_file(self) -> pathlib.Path:
        return self._db_file or self.state_tree / f"{self.app_name}{self.db_suffix}"

    @db_file.setter
    def db_file(self, value):
        self._db_file = value

    def load(self):
        with self.toml_file.open("rb") as f:
            data = tomllib.load(f)
        for k, v in data.items():
            n = k.replace("-", "_")
            if n.endswith("_tree") or n.endswith("_file"):
                v = pathlib.Path(v)
            setattr(self, n, v)


def _id_for_table(tablename: str) -> str:
    return "id"


def _refid_for_table(tablename: str, qualifier: str = None) -> str:
    if qualifier:
        raise NotImplementedError("what to do with a qualifier?", tablename, qualifier)
    return tablename + "_" + _id_for_table(tablename)


def _reference_other_tables(referred_tables: list[str]) -> dict[str, str]:
    return {
        _refid_for_table(n): "INTEGER REFERENCES " + n + "(" + _id_for_table(n) + ")"
        for n in referred_tables
    }


FFOD_DB_TABLES = {
    FFOD_DB_NAME_USB: {
        FFOD_DB_NAME_FIRSTSEENUTC: "TEXT DEFAULT CURRENT_TIMESTAMP",
        FFOD_DB_NAME_VENDOR: "TEXT",
        FFOD_DB_NAME_MODEL: "TEXT",
        FFOD_DB_NAME_SERIAL: "TEXT",
        FFOD_DB_NAME_SIZE: "INTEGER",
    },
    FFOD_DB_NAME_VOL: {
        FFOD_DB_NAME_LABEL: "TEXT",
        FFOD_DB_NAME_UUID: "TEXT",
        FFOD_DB_NAME_SIZE: "INTEGER",
    }
    | _reference_other_tables([FFOD_DB_NAME_USB]),
}
FFOD_DB_TABLE_UNIQUES = {
    FFOD_DB_NAME_USB: [
        [FFOD_DB_NAME_VENDOR, FFOD_DB_NAME_SERIAL],
    ],
    FFOD_DB_NAME_VOL: [
        [FFOD_DB_NAME_LABEL, FFOD_DB_NAME_UUID],
    ],
}
FFOD_DB_SCHEMA = {
    tablename: "CREATE TABLE "
    + tablename
    + " ("
    + ", ".join(
        [_id_for_table(tablename) + " INTEGER PRIMARY KEY"]
        + [colname + " " + coltype for colname, coltype in columns.items()]
        + [
            "UNIQUE(" + ", ".join(colnames) + ")"
            for colnames in FFOD_DB_TABLE_UNIQUES.get(tablename, [])
        ]
    )
    + ")"
    for tablename, columns in FFOD_DB_TABLES.items()
}
FFOD_DB_FIND_SQLS = {
    tablename: [
        "SELECT * FROM "
        + tablename
        + " WHERE "
        + " AND ".join([colname + " = :" + colname for colname in colnames])
        for colnames in FFOD_DB_TABLE_UNIQUES.get(tablename, [])
    ]
    for tablename in FFOD_DB_TABLES.keys()
}


class Database:
    def __init__(
        self,
        dbfile: pathlib.Path,
        schemadef: dict[str, str] = FFOD_DB_SCHEMA,
    ):
        self.dbfile = pathlib.Path(dbfile)
        self.schemadef = copy.copy(schemadef)
        self.con = sqlite3.connect(self.dbfile)
        self.con.row_factory = sqlite3.Row
        self.ensure_schema()

    def _execute(
        self,
        cur: sqlite3.Cursor,
        sql: str,
        parameters: collections.abc.Sequence | collections.abc.Mapping = (),
    ) -> sqlite3.Cursor:
        prefix = "--"
        print(prefix, sql)
        if "items" in dir(parameters):
            for k, v in parameters.items():
                print(prefix, prefix, k, repr(v))
        else:
            for v in parameters:
                print(prefix, prefix, repr(v))
        if parameters:
            print(prefix, prefix)
        return cur.execute(sql, parameters)

    def _fetchall(self, cur: sqlite3.Cursor) -> list[dict[str, object]]:
        return [dict(row) for row in cur.fetchall()]

    def _find_one(
        self, cur: sqlite3.Cursor, tablename: str, data: dict[str, object]
    ) -> int | None:
        found = []
        for find_sql in FFOD_DB_FIND_SQLS.get(tablename, []):
            self._execute(cur, find_sql, data)
            found.extend(self._fetchall(cur))
        if found:
            if len(found) == 1:
                return found[0][_id_for_table(tablename)]
            raise NotImplementedError("what to do if multiple found?", tablename, found)
        return None

    def _insert_one(
        self, cur: sqlite3.Cursor, tablename: str, data: dict[str, object]
    ) -> dict[str, object]:
        insert_colnames = list(data.keys())
        insert_sql = (
            "INSERT INTO "
            + tablename
            + "("
            + ", ".join(insert_colnames)
            + ") VALUES("
            + ", ".join([":" + n for n in insert_colnames])
            + ") RETURNING *"
        )
        self._execute(cur, insert_sql, data)
        inserted = self._fetchall(cur)
        if inserted:
            if len(inserted) == 1:
                return inserted[0]
            raise NotImplementedError(
                "what to do if multiple inserted?", tablename, inserted
            )
        raise NotImplementedError(
            "what to do if nothing inserted?", tablename, inserted
        )

    def _find_or_insert_one(self, tablename: str, data: dict[str, object]) -> int:
        cur = self.con.cursor()
        try:
            found_id = self._find_one(cur, tablename, data)
            if found_id is not None:
                return found_id
            inserted = self._insert_one(cur, tablename, data)
            self.con.commit()
            return inserted[_id_for_table(tablename)]
        finally:
            cur.close()

    def ensure_schema(self):
        cur = self.con.cursor()
        try:
            existing_schema: dict[str, str] = {}
            self._execute(cur, "SELECT type, name, sql FROM sqlite_schema")
            for t, n, s in cur.fetchall():
                if t == "index" and s is None:
                    continue
                if t == "table" and s is not None:
                    pass
                else:
                    raise NotImplementedError(
                        "unhandled DDL for existing schema", t.upper(), n, s
                    )
                existing_schema[n] = s

            missing = []
            mismatch = []
            for expected_name, expected_sql in self.schemadef.items():
                if expected_name not in existing_schema:
                    missing.append((expected_name, expected_sql))
                else:
                    existing_sql = existing_schema[expected_name]
                    if expected_sql != existing_sql:
                        mismatch.append((expected_name, expected_sql, existing_sql))

            extra = []
            for existing_name, existing_sql in existing_schema.items():
                if existing_name not in self.schemadef:
                    extra.append((existing_name, existing_sql))

            created = []
            for expected_name, expected_sql in missing:
                self._execute(cur, expected_sql)
                created.append((expected_name, expected_sql))

        finally:
            cur.close()

        if existing_schema:
            print("---- Existing schema")
            for existing_sql in existing_schema.values():
                print(existing_sql)

        if created:
            print("---- Created")
            for _, created_sql in missing:
                print(created_sql)

        if mismatch:
            print("---- Mismatched")
            # TODO use an actionable presentation
            for expected_name, expected_sql, existing_sql in mismatch:
                print("mismatch:", expected_name)
                print("expected:", expected_sql)
                print("existing:", existing_sql)
                for opcode, a0, a1, b0, b1 in difflib.SequenceMatcher(
                    None, expected_sql, existing_sql
                ).get_opcodes():
                    print("-", opcode, a0, a1, b0, b1)
                print()

        if extra:
            for _, existing_sql in extra:
                print("---- Extra")
                print(existing_sql)

        if existing_schema or created or mismatch or extra:
            print("----")

    def note_usb_device(self, usbdev: BlockDevice) -> int:
        data = {
            colname: val
            for colname, val in [
                (FFOD_DB_NAME_VENDOR, usbdev.vendor),
                (FFOD_DB_NAME_MODEL, usbdev.model),
                (FFOD_DB_NAME_SERIAL, usbdev.serial),
                (FFOD_DB_NAME_SIZE, usbdev.size.sizebytes),
            ]
            if val
        }
        return self._find_or_insert_one(FFOD_DB_NAME_USB, data)

    def note_volume(self, vol: BlockDevice, usbid: int) -> int:
        data = {
            colname: val
            for colname, val in [
                (FFOD_DB_NAME_LABEL, vol.label),
                (FFOD_DB_NAME_UUID, vol.uuid),
                (FFOD_DB_NAME_SIZE, vol.size.sizebytes),
                (_refid_for_table(FFOD_DB_NAME_USB), usbid),
            ]
            if val
        }
        return self._find_or_insert_one(FFOD_DB_NAME_VOL, data)


if __name__ == "__main__":
    main()
