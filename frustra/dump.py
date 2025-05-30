from __future__ import annotations

import collections.abc
import dataclasses
import inspect
import sys

from .elide import elide_repr


def print_stderr(*args, **kwargs):
    kwargs = dict(kwargs)
    kwargs["file"] = sys.stderr
    print(*args, **kwargs)


def dump(*args, print=print_stderr) -> None:
    frames = inspect.stack()
    print()
    if frames[1].function != "<module>":
        print("++", frames[1].function)
    indent = ["++", "--"]
    for arg in args:
        if not dump_object(arg, indent=indent, print=print):
            print(*indent, elide_repr(arg))
        print("++")


def dump_object(obj, indent=[], print=print_stderr) -> bool:
    if type(obj) in [None, str, bytes]:
        print(*indent, elide_repr(obj))
        return True
    r = repr(obj)
    er = elide_repr(obj)
    if r == er:
        print(*indent, r)
        return True
    else:
        for df in [
            dump_mapping,
            dump_sequence_or_set,
            dump_exception,
            dump_dataclass_instance,
        ]:
            if df(obj=obj, indent=indent, print=print):
                return True
    return False


def dump_mapping(obj, indent=[], print=print_stderr) -> bool:
    if isinstance(obj, collections.abc.Mapping):
        if obj:
            w = max([len(str(k)) for k in obj.keys()])
            fmt = f"{{k:{w}}} :"
            subindent = indent + ["--"]
            for k, v in obj.items():
                kstr = fmt.format(k=str(k))
                ksubindent = indent + [kstr]
                if not dump_object(v, indent=ksubindent, print=print):
                    print(*ksubindent, elide_repr(v))
            print(*indent)
        else:
            print(*indent, obj)
        return True
    else:
        return False


def dump_sequence_or_set(obj, indent=[], print=print_stderr) -> bool:
    if isinstance(obj, collections.abc.Set):
        try:
            obj = sorted(obj)
        except TypeError as te:
            obj = list(obj)
    if isinstance(obj, collections.abc.Sequence):
        if obj:
            subindent = indent + ["·"]
            for v in obj:
                if not dump_object(v, indent=subindent, print=print):
                    print(*subindent, elide_repr(v))
            print(*indent)
        else:
            print(*indent, obj)
        return True
    else:
        return False


def dump_exception(obj, indent=[], print=print_stderr) -> bool:
    if isinstance(obj, BaseException):
        print(*indent, type(obj).__name__)
        subindent = indent + ["-"]
        for arg in obj.args:
            dump_object(arg, indent=subindent, print=print)
        print(*indent)
        return True
    else:
        return False


def dump_dataclass_instance(obj, indent=[], print=print_stderr) -> bool:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        print(*indent, type(obj).__name__)
        return dump_mapping(
            {k: v for k, v in dataclasses.asdict(obj).items() if v is not None},
            indent=indent + [""],
            print=print,
        )
    else:
        return False
