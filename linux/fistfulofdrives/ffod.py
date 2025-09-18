from __future__ import annotations

import dataclasses
import functools
import json
import keyword
import pathlib
import shlex
import subprocess
import sys
import types
import typing
import uuid


FFOD_MOUNT_TREE = pathlib.Path("/media/ffod")
FFOD_IGNORE_ME_FILE = "ffod.ignore.txt"


def main():
    if "--regenerate-block-device-class-from-lsblk" in sys.argv:
        _regenerate_block_device_class_from_lsblk()
        return

    vols = get_volumes_on_usb_devices()
    vols_that_need_remount: list[tuple[BlockDevice, pathlib.Path]] = []
    vols_with_bad_mountpoint: list[tuple[BlockDevice, pathlib.Path]] = []
    vols_that_need_mountpoint: list[tuple[BlockDevice, pathlib.Path]] = []
    vols_that_need_mount: list[tuple[BlockDevice, pathlib.Path]] = []
    good_vols: list[tuple[BlockDevice, pathlib.Path]] = []
    for vol in vols:
        allgood = True
        expected_mountpoint = FFOD_MOUNT_TREE / f"{vol.label},{vol.uuid}"
        actual_mountpoint = pathlib.Path(vol.mountpoint) if vol.mountpoint else None
        if not expected_mountpoint.is_dir(follow_symlinks=False):
            allgood = False
            if expected_mountpoint.exists():
                vols_with_bad_mountpoint.append((vol, expected_mountpoint))
            else:
                vols_that_need_mountpoint.append((vol, expected_mountpoint))
        if actual_mountpoint and actual_mountpoint != expected_mountpoint:
            allgood = False
            vols_that_need_remount.append((vol, expected_mountpoint))
        elif not actual_mountpoint:
            allgood = False
            vols_that_need_mount.append((vol, expected_mountpoint))
        if allgood:
            good_vols.append((vol, expected_mountpoint))

    dump_table([[vol.name, vol.fstype, expmt] for vol, expmt in good_vols])

    if vols_with_bad_mountpoint:
        print("!!!! FIX MOUNTPOINT (should be directory) !!!!")
        dump_table([[vol.name, expmt] for vol, expmt in vols_with_bad_mountpoint])
        return
    if vols_that_need_remount:
        print("!!!! UNMOUNT AND REMOUNT !!!!")
        dump_table(
            [
                [vol.name, vol.mountpoint, expmt]
                for vol, expmt in vols_with_bad_mountpoint
            ]
        )
        return
    if vols_that_need_mountpoint:
        print("# need mountpoint")
        dump_table([["#", vol.name, expmt] for vol, expmt in vols_that_need_mountpoint])
        for vol, expmt in vols_that_need_mountpoint:
            print(f"sudo mkdir -v {shlex.quote(str(expmt))}    #  {vol.name}")
        print()
    if vols_that_need_mount:
        print("# need mount")
        dump_table([["#", vol.name, expmt] for vol, expmt in vols_that_need_mount])
        for vol, expmt in vols_that_need_mount:
            print(f"sudo mount -v UUID={vol.uuid} {shlex.quote(str(expmt))}")
        print()


def get_volumes_on_usb_devices() -> list[BlockDevice]:
    usbdevs = get_usb_devices()
    candidates = list_block_devices(devices=[d.path for d in usbdevs])
    vols = [bd for bd in candidates if is_volume(bd) and not ignore_volume(bd)]
    return vols


def get_usb_devices() -> list[BlockDevice]:
    trankey, pathkey = (BLOCKDEVICE_NAME_TO_KEY[n] for n in ["tran", "path"])
    return list_block_devices(outputkeys=[pathkey, trankey], filter=FILTER_USB)


def is_volume(bd: BlockDevice) -> bool:
    if bd.fstype is not None:
        return True
    return False


IGNORE_PARTTYPE_UUIDS = {
    uuid.UUID("c12a7328-f81f-11d2-ba4b-00a0c93ec93b"): ("EFI System Partition", "ESP"),
    uuid.UUID("e3c9e316-0b5c-4db8-817d-f92df00215ae"): (
        "Microsoft Reserved Partition",
        "MSR",
    ),
}
IGNORE_FSTYPES = {
    "ntfs": "NTFS",
}


def ignore_volume(bd: BlockDevice) -> bool:
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
            and (pathlib.Path(bd.mountpoint) / FFOD_IGNORE_ME_FILE).exists()
        ):
            return True
    except PermissionError:
        pass

    return False


METADATA_HOLDER = "holder"
METADATA_KEY = "key"
METADATA_DESC = "desc"
LSBLK_KNOWN_PLURALS = {"FSROOTS", "MOUNTPOINTS"}


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
FILTER_USB, FILTER_NOT_USB = (
    f'{BLOCKDEVICE_NAME_TO_KEY["tran"]} {op} "usb"' for op in ["eq", "ne"]
)


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


if __name__ == "__main__":
    main()
