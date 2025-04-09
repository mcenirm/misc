from __future__ import annotations

import dataclasses
import inspect

from .elide import elide_repr


def dump(*args) -> None:
    frames = inspect.stack()
    print()
    print("++", frames[1].function)
    indent = ["++", "--"]
    for arg in args:
        print(*indent, elide_repr(arg))
        dump_dataclass_instance(arg, indent=indent)
        print("++")


def dump_dataclass_instance(obj, indent=[]) -> bool:
    try:
        fs = dataclasses.fields(obj)
        w = max([len(f.name) for f in fs])
        fmt = f"{{n:{w}}}"
        for f in fs:
            a = getattr(obj, f.name)
            print(*indent, fmt.format(n=f.name), elide_repr(a))
            dump_dataclass_instance(a, indent + ["--"])
        return True
    except TypeError as te:
        return False
