import argparse
import collections.abc
import dataclasses
import doctest
import inspect
import re
import shlex
import traceback
import typing


class _arguments_for_add_argument(typing.NamedTuple):
    name_or_flags: tuple[str, ...]
    kwargs: dict[str, typing.Any]

    def __str__(self) -> str:
        s = ", ".join(map(repr, self.name_or_flags))
        for k, v in sorted(self.kwargs.items()):
            if isinstance(v, type):
                qname = getattr(v, "__qualname__", v.__name__)
                modname = getattr(v, "__module__", "builtins")
                if modname != "builtins":
                    qname = modname + "." + qname
                v = qname
            else:
                v = repr(v)
            s += f", {k}={v}"
        return s


def _arguments_from_function(
    f: collections.abc.Callable[..., typing.Any],
) -> list[_arguments_for_add_argument]:
    """
    >>> t = lambda f: [str(a) for a in _arguments_from_function(f)]

    >>> def simple(a: int, b: str): ...
    >>> t(simple)
    ["'--a', required=True, type=int", "'--b', required=True, type=str"]

    >>> def withdefault(c: str="something"): ...
    >>> t(withdefault)
    ["'--c', default='something', type=str"]

    >>> def withbool(d: bool=False): ...
    >>> t(withbool)
    ["'--d', action='store_true'"]

    >>> def withbooldefaulttrue(e: bool=True): ...
    >>> t(withbooldefaulttrue)
    ["'--e', action='store_false'"]

    """

    args = []
    s = inspect.signature(f)
    h = typing.get_type_hints(f)
    for name, param in s.parameters.items():
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue
        opt = "--" + name.replace("_", "-")
        kw: dict[str, typing.Any] = {}
        param_type = h.get(name, str)
        if param_type is bool:
            if param.default is False or param.default is inspect.Parameter.empty:
                kw["action"] = "store_true"
            else:
                kw["action"] = "store_false"
        else:
            kw["type"] = param_type
            if param.default is not inspect.Parameter.empty:
                kw["default"] = param.default
            else:
                kw["required"] = True
        args.append(
            _arguments_for_add_argument(
                name_or_flags=(opt,),
                kwargs=kw,
            )
        )
    return args


def argument_parser_from_function(
    f: collections.abc.Callable[..., typing.Any],
) -> argparse.ArgumentParser:
    argargs = _arguments_from_function(f)
    ap = argparse.ArgumentParser(
        description=inspect.getdoc(f),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    for aa in argargs:
        ap.add_argument(*aa.name_or_flags, **aa.kwargs)
    return ap


@dataclasses.dataclass
class ParsedShebangLine:
    line: str
    interpreter: str
    args: list[str]
    env: str
    env_opts: list[tuple[str, str]]
    env_vars: list[tuple[str, str]]


def parse_shebang(line: str) -> ParsedShebangLine | None:
    if line and line.startswith("#!") and (shebang := line[2:].strip()):
        if re.compile(r"\s*/?env\s+-S").match(shebang):
            raise NotImplementedError(
                line,
                "fancy env -S string parsing not implemented yet",
            )
        env = ""
        env_opts = []
        env_vars = []
        interpreter, *args = shlex.split(shebang)
        if interpreter == "env" or interpreter.endswith("/env"):
            env = interpreter
            interpreter = ""
            while args:
                opt = args.pop(0)
                match opt:
                    case "--":
                        if args:
                            interpreter = args.pop(0)
                        break
                    case opt if opt.startswith("--"):
                        raise NotImplementedError(
                            line,
                            "env long options not implemented yet",
                        )
                    case "-S":
                        raise NotImplementedError(
                            line,
                            "env fancy -S string parsing not implemented yet",
                        )
                    case "-C" | "-u" | "-P" | "-a":
                        # common:         -C, -u
                        # macos:          -P
                        # GNU coreutils:  -a
                        arg = args.pop(0) if args else ""
                        env_opts.append((opt, arg))
                    case opt if opt.startswith("-"):
                        env_opts.append((opt, ""))
                    case opt if "=" in opt:
                        n, v = opt.split("=", maxsplit=1)
                        env_vars.append((n, v))
                    case _:
                        interpreter = opt
                        break
        return ParsedShebangLine(
            line=line,
            interpreter=interpreter,
            args=args,
            env=env,
            env_opts=env_opts,
            env_vars=env_vars,
        )
    else:
        return None


def meighn(
    actual_function: collections.abc.Callable,
    args: list[str] | None = None,
):
    ap = argument_parser_from_function(actual_function)
    ns = ap.parse_args(args).__dict__
    try:
        return actual_function(**ns)
    except NotImplementedError as e:
        print(type(e).__name__)
        for a in e.args:
            r = a
            if r is not None:
                r = repr(r)
                if "\n" in r:
                    r = repr(str(a))
                r = r[:80]
            print(" ●", r)
        print()
        print(traceback.format_exception(e)[-2])
        print()


if __name__ == "__main__":
    doctest.testmod(optionflags=doctest.ELLIPSIS | doctest.FAIL_FAST)
