import argparse
import collections.abc
import dataclasses
import inspect
import re
import shlex
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
