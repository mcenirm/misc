import argparse
import collections.abc
import inspect
import typing


def argument_parser_from_function(
    f: collections.abc.Callable[..., typing.Any],
) -> argparse.ArgumentParser:
    s = inspect.signature(f)
    h = typing.get_type_hints(f)
    _ = h.pop("return", None)
    ap = argparse.ArgumentParser(
        description=f.__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    for n, t in h.items():
        opt = "--" + n.replace("_", "-")
        kw = dict(type=t)
        if s.parameters[n].default is not inspect.Parameter.empty:
            kw["default"] = s.parameters[n].default
            kw["help"] = n.replace("_", " ")
        ap.add_argument(opt, **kw)
    return ap
