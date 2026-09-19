import ast
import dataclasses
import fnmatch
import glob
import inspect
import json
import pathlib
import subprocess
import sys
import types
import typing

import black
import dacite
from frozendict import frozendict

import frustra.cmds
import frustra.strings


@dataclasses.dataclass(frozen=True)
class WrapperArgument:
    id: str
    type: type | types.UnionType
    default: typing.Any
    cond: str | None
    argsappend: str
    is_array: bool = False

    def get_signature(self) -> str:
        parts = [self.id, ":"]
        if isinstance(self.type, (types.UnionType, types.GenericAlias)):
            typestr = str(self.type)
        else:
            typestr = self.type.__qualname__
            if self.type not in (str, bool):
                raise NotImplementedError(
                    "not sure how to make signature for type (cf __qualname__)",
                    self.type,
                    type(self.type),
                    typestr,
                )
        parts.append(typestr)
        if self.default != inspect.Parameter.empty:
            parts.append("=")
            parts.append(repr(self.default))
        return " ".join(parts)


@dataclasses.dataclass(frozen=True)
class ComposerApplication:
    name: str
    version: str


@dataclasses.dataclass(frozen=True)
class ComposerNamespace:
    id: str
    commands: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class ComposerCommandArgument:
    name: str
    is_required: bool
    is_array: bool
    description: str
    default: str | None


def _composer_command_name_to_function_name(name: str) -> str:
    return frustra.strings.str_to_identifier(f"composer-{name}")


def _composer_arg_name_to_python_id(name: str) -> str:
    return frustra.strings.str_to_identifier(name)


def _composer_opt_name_to_python_id(name: str) -> str:
    return frustra.strings.str_to_identifier(name.removeprefix("--"))


def _opt_bool_default_false(
    composer_option_name: str,
) -> WrapperArgument:
    opt_id = _composer_opt_name_to_python_id(composer_option_name)
    return WrapperArgument(
        id=opt_id,
        type=bool,
        default=False,
        cond=opt_id,
        argsappend=f"'{composer_option_name}'",
    )


def _opt_bool_default_true(composer_option_name: str) -> WrapperArgument:
    opt_id = _composer_opt_name_to_python_id(composer_option_name.removeprefix("--no-"))
    return WrapperArgument(
        id=opt_id,
        type=bool,
        default=True,
        cond=f"not {opt_id}",
        argsappend=f"'{composer_option_name}'",
    )


_COMPOSER_OPTION_QUIET = "--quiet"
_COMPOSER_OPTION_VERBOSE = "--verbose"
_COMPOSER_OPTION_NO_PLUGINS = "--no-plugins"
_COMPOSER_OPTION_NO_SCRIPTS = "--no-scripts"
_COMPOSER_OPTION_WORKING_DIR = "--working-dir"
_COMPOSER_OPTION_WORKING_DIR_ID = _composer_opt_name_to_python_id(
    _COMPOSER_OPTION_WORKING_DIR
)
_COMPOSER_OPTION_NO_CACHE = "--no-cache"
_COMPOSER_GLOBAL_OPTIONS = {
    _COMPOSER_OPTION_QUIET: _opt_bool_default_false(_COMPOSER_OPTION_QUIET),
    _COMPOSER_OPTION_VERBOSE: _opt_bool_default_false(_COMPOSER_OPTION_VERBOSE),
    _COMPOSER_OPTION_NO_PLUGINS: _opt_bool_default_true(_COMPOSER_OPTION_NO_PLUGINS),
    _COMPOSER_OPTION_NO_SCRIPTS: _opt_bool_default_true(_COMPOSER_OPTION_NO_SCRIPTS),
    _COMPOSER_OPTION_WORKING_DIR: WrapperArgument(
        id=_COMPOSER_OPTION_WORKING_DIR_ID,
        type=str | pathlib.Path | None,
        default=None,
        cond=f"{_COMPOSER_OPTION_WORKING_DIR_ID} is not None",
        argsappend=f"f'{_COMPOSER_OPTION_WORKING_DIR}={{{_COMPOSER_OPTION_WORKING_DIR_ID}}}'",
    ),
    _COMPOSER_OPTION_NO_CACHE: _opt_bool_default_true(_COMPOSER_OPTION_NO_CACHE),
}

_COMPOSER_IGNORE_OPTIONS = [
    "--help",
    "--version",
    "--ansi",
    "--no-ansi",
    "--no-interaction",
    "--profile",
]


@dataclasses.dataclass(frozen=True)
class ComposerCommandOption:
    name: str
    shortcut: str
    accept_value: bool
    is_value_required: bool
    is_multiple: bool
    description: str
    default: bool | str | None
    is_global: bool = dataclasses.field(init=False)
    ignore: bool = dataclasses.field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "is_global", self.name in _COMPOSER_GLOBAL_OPTIONS)
        object.__setattr__(self, "ignore", self.name in _COMPOSER_IGNORE_OPTIONS)


@dataclasses.dataclass(frozen=True)
class ComposerCommandDefinition:
    arguments: frozendict[str, ComposerCommandArgument]
    options: frozendict[str, ComposerCommandOption]


@dataclasses.dataclass(frozen=True)
class ComposerCommand:
    name: str
    description: str
    usage: tuple[str, ...]
    help: str
    definition: ComposerCommandDefinition
    hidden: bool


@dataclasses.dataclass(frozen=True)
class ComposerListOutput:
    application: ComposerApplication
    commands: tuple[ComposerCommand, ...]
    namespaces: tuple[ComposerNamespace, ...]


def _from_composer_json_output[T](
    args: list[str],
    data_class: type[T],
    save_json: pathlib.Path | None = None,
) -> T:
    jsontext = subprocess.check_output(
        [
            "composer",
            "--format=json",
            *args,
        ],
        text=True,
    )
    if save_json is not None:
        save_json = pathlib.Path(save_json)
        with save_json.open("wt", encoding="utf-8") as out:
            subprocess.run(
                [sys.executable, "-m", "json.tool", "--indent", "4"],
                input=jsontext,
                text=True,
                stdout=out,
                check=True,
            )
    return dacite.from_dict(
        data_class,
        json.loads(jsontext),
        config=dacite.Config(
            type_hooks={
                str | None: lambda v: None if v == [] else v,
                bool | str | None: lambda v: None if v == [] else v,
                frozendict[str, ComposerCommandArgument]: frozendict,
                frozendict[str, ComposerCommandOption]: frozendict,
                tuple[str, ...]: tuple,
                tuple[ComposerCommand, ...]: tuple,
                tuple[ComposerNamespace, ...]: tuple,
            },  # type: ignore
            strict=True,
        ),
    )


def composer_help_to_python_function(
    command_name: str,
    scratch_dir: pathlib.Path = pathlib.Path("scratch"),
):
    scratch_dir = pathlib.Path(scratch_dir)
    scratch_dir.mkdir(exist_ok=True)

    if glob.has_magic(command_name):
        commands = [
            c
            for c in _from_composer_json_output(
                ["list"],
                ComposerListOutput,
                save_json=scratch_dir / "list.json",
            ).commands
            if fnmatch.fnmatch(c.name, command_name)
        ]
    else:
        commands = [
            _from_composer_json_output(
                [
                    "help",
                    command_name,
                ],
                ComposerCommand,
                save_json=scratch_dir / f"{command_name}.json",
            )
        ]

    for info in commands:
        fname = _composer_command_name_to_function_name(info.name)

        fargs = []
        for arg_name, arg in info.definition.arguments.items():
            arg_id = _composer_arg_name_to_python_id(arg.name)

            if (
                arg.is_required is True
                and arg.is_array is False
                and arg.default is None
            ):
                fargs.append(
                    WrapperArgument(
                        id=arg_id,
                        type=str,
                        default=inspect.Parameter.empty,
                        cond=None,
                        argsappend=arg_id,
                    )
                )

            elif (
                arg.is_required is False
                and arg.is_array is True
                and arg.default is None
            ):
                fargs.append(
                    WrapperArgument(
                        id=arg_id,
                        type=list[str],
                        default=[],
                        cond=arg_id,
                        argsappend="array_item",
                        is_array=arg.is_array,
                    )
                )

            elif (
                arg.is_required is False
                and arg.is_array is False
                and isinstance(arg.default, str)
            ):
                fargs.append(
                    WrapperArgument(
                        id=arg_id,
                        type=str | None,
                        default=arg.default,
                        cond=f"{arg_id} is not None and {arg_id} != {arg.default!r}",
                        argsappend=arg_id,
                    )
                )

            elif (
                arg.is_required is False
                and arg.is_array is False
                and arg.default is None
            ):
                fargs.append(
                    WrapperArgument(
                        id=arg_id,
                        type=str | None,
                        default=None,
                        cond=f"{arg_id} is not None",
                        argsappend=arg_id,
                    )
                )

            elif (
                arg.is_required is True
                and arg.is_array is True
                and arg.default is None
                and True
            ):
                fargs.append(
                    WrapperArgument(
                        id=arg_id,
                        type=list[str],
                        default=inspect.Parameter.empty,
                        cond=None,
                        argsappend="array_item",
                    )
                )

            else:
                raise NotImplementedError(
                    "unexpected argument combination",
                    "-------------",
                    *info.__dict__.items(),
                    "-------------",
                    *arg.__dict__.items(),
                )

        fopts = []
        for opt_name, opt in info.definition.options.items():
            if opt.name in _COMPOSER_IGNORE_OPTIONS:
                continue
            if opt.name in _COMPOSER_GLOBAL_OPTIONS:
                fopts.append(_COMPOSER_GLOBAL_OPTIONS[opt.name])
                continue

            opt_id = _composer_opt_name_to_python_id(opt.name)
            opt_default_repr = repr(opt.default)

            if (
                opt.accept_value is True
                and opt.is_value_required is True
                and opt.is_multiple is False
                and (opt.default is None or isinstance(opt.default, str))
            ):
                fopts.append(
                    WrapperArgument(
                        id=opt_id,
                        type=str | None if opt.default is None else str,
                        default=opt.default,
                        cond=f"{opt_id} is not None"
                        + (
                            ""
                            if opt.default is None
                            else f" and {opt_id} != {opt_default_repr}"
                        ),
                        argsappend=f"f'{opt.name}={{{opt_id}}}'",
                    )
                )

            elif (
                opt.accept_value is True
                and opt.is_value_required is True
                and opt.is_multiple is True
                and opt.default is None
            ):
                fopts.append(
                    WrapperArgument(
                        id=opt_id,
                        type=list[str],
                        default=[],
                        cond=f"{opt_id} is not None",
                        argsappend=f"f'{opt.name}={{array_item}}'",
                        is_array=opt.is_multiple,
                    )
                )

            elif (
                opt.accept_value is True
                and opt.is_value_required is False
                and opt.is_multiple is False
                and opt.default is False
            ):
                fopts.append(
                    WrapperArgument(
                        id=opt_id,
                        type=bool,
                        default=opt.default,
                        cond=opt_id,
                        argsappend=f"f'{opt.name}={{{opt_id}}}' if {opt_id} else '{opt.name}'",
                    )
                )

            elif (
                opt.accept_value is False
                and opt.is_value_required is False
                and opt.is_multiple is False
                and (opt.default is None or isinstance(opt.default, bool))
            ):
                fopts.append(
                    WrapperArgument(
                        id=opt_id,
                        type=bool,
                        default=opt.default,
                        cond=f"not {opt_id}" if opt.default else opt_id,
                        argsappend=f"'{opt.name}'",
                    )
                )

            else:
                raise NotImplementedError(
                    "unexpected option combination",
                    "-------------",
                    *info.__dict__.items(),
                    "-------------",
                    *opt.__dict__.items(),
                )

        indent = " " * 4
        flines = []
        flines.append(f"def {fname}(")
        for a in fargs + fopts:
            flines.append(indent + a.get_signature() + ",")
        flines.append("):")
        fdocstr_lines = [info.description]
        if info.usage:
            fdocstr_lines.append("")
            fdocstr_lines.append("Usage:")
            fdocstr_lines.extend(info.usage)
            fdocstr_lines.append("")
        fdocstr = "\n".join([repr(line)[1:-1] for line in fdocstr_lines])
        flines.append(indent + "'''" + fdocstr + "'''")
        flines.append(indent + "args = []")

        statement_list = list(fopts)
        if fargs:
            statement_list.append(
                WrapperArgument(
                    id="",
                    type=type(None),
                    default=inspect.Parameter.empty,
                    cond=None,
                    argsappend="'--'",
                )
            )
            statement_list.extend(fargs)
        for a in statement_list:
            ind = indent
            if a.cond is not None:
                flines.append(ind + "if " + a.cond + ":")
                ind += indent
                if a.is_array:
                    flines.append(ind + f"for array_item in {a.id}:")
                    ind += indent
            flines.append(ind + f"args.append({a.argsappend})")

        flines.append(indent + f"_composer_run('{info.name}', args)")

        fsrc = "\n".join(flines) + "\n"
        ftree = ast.parse(fsrc)
        (scratch_dir / f"{info.name}.ast.txt").write_text(ast.dump(ftree, indent=4))
        fsrc2 = ast.unparse(ftree)
        formatted_src = black.format_str(fsrc2, mode=black.Mode())
        (scratch_dir / f"{fname}.py").write_text(formatted_src)


class TODO(NotImplementedError): ...


if __name__ == "__main__":
    frustra.cmds.meighn(composer_help_to_python_function)
