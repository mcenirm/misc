import shlex
import sys
import textwrap
import uuid
from pathlib import Path
from typing import TextIO


VISOEXT = ".viso"
USAGE = textwrap.dedent(
    f"""
    Usage: {sys.argv[0]} file1 [files...]
    Create simple VISO
    Options:
        -o out[{VISOEXT}]   set output filename
            (`-` for stdout, default based on file1)
    """
).strip()


def create_simple_viso(
    *contents: Path,
    viso: Path | TextIO | None = None,
) -> Path | None:
    """Create a simple virtual ISO (VISO) file

    See <https://docs.oracle.com/en/virtualization/virtualbox/7.0/user/AdvancedTopics.html#viso>
    """
    if viso is None:
        viso = contents[0]
    if isinstance(viso, Path):
        viso = viso.with_suffix(VISOEXT)
        out = viso.open("w")
        volume_id = viso
    else:
        out = viso
        volume_id = contents[0]
    volume_id = volume_id.stem
    try:
        print(f"--iprt-iso-maker-file-marker-bourne-sh {uuid.uuid4()}", file=out)
        print(f"--volume-id={volume_id}", file=out)
        for content in contents:
            print(shlex.quote(content.resolve().as_posix()), file=out)
    finally:
        if isinstance(viso, Path):
            out.close()
    if isinstance(viso, Path):
        return viso


def main():
    viso = None
    args = sys.argv[1:]
    while len(args) > 0:
        match args[0]:
            case "--":
                args.pop(0)
                break
            case "-o":
                args.pop(0)
                if len(args) < 1:
                    print("Error: Missing argument to `-o`")
                    usage_and_exit()
                viso = args.pop(0)
            case _:
                if args[0][0] == "-":
                    usage_and_exit()
                break
    if len(args) < 1:
        usage_and_exit()
    if viso == "-":
        viso = sys.stdout
    elif viso is not None:
        viso = Path(viso)
    create_simple_viso(
        *list(map(Path, args)),
        viso=viso,
    )


def usage_and_exit():
    print(USAGE)
    sys.exit(1)


if __name__ == "__main__":
    main()
