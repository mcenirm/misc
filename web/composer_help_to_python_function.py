import ast
import collections
import dataclasses
import fnmatch
import glob
import json
import pathlib
import subprocess
import sys
import typing

import black
import dacite
import frustra.cmds
import frustra.strings
from frozendict import frozendict


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


COMPOSER_GLOBAL_OPTIONS = [
    "--help",
    "--quiet",
    "--verbose",
    "--version",
    "--ansi",
    "--no-ansi",
    "--no-interaction",
    "--profile",
    "--no-plugins",
    "--no-scripts",
    "--working-dir",
    "--no-cache",
]
COMPOSER_IGNORE_OPTIONS = [
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
        object.__setattr__(self, "is_global", self.name in COMPOSER_GLOBAL_OPTIONS)
        object.__setattr__(self, "ignore", self.name in COMPOSER_IGNORE_OPTIONS)


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


@dataclasses.dataclass(frozen=True)
class WrapperArgument:
    id: str
    type: type
    default: str
    cond: str
    argsappend: str


def composer_help_id_to_python_id(id: str) -> str:
    return frustra.strings.snake_case(id)


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
            },
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
        arg_name_to_command_list = collections.defaultdict(list)
        opt_name_to_command_list = collections.defaultdict(list)
        for c in commands:
            for n, a in c.definition.arguments.items():
                arg_name_to_command_list[n].append(c.name)
            for n, o in c.definition.options.items():
                opt_name_to_command_list[n].append(c.name)
        raise TODO(
            *sorted((len(v), k) for k, v in arg_name_to_command_list.items()),
            "-------------",
            *sorted((len(v), k) for k, v in opt_name_to_command_list.items()),
            "-------------",
            *commands[0].definition.options["ansi"].__dict__.items(),
            "-------------",
            *commands[0].definition.options["no-ansi"].__dict__.items(),
        )
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
        fname = composer_help_id_to_python_id("composer-" + info.name)
        fargs = []

        for arg_name, arg in info.definition.arguments.items():
            arg_name = composer_help_id_to_python_id(arg_name)

            if (
                arg.is_required is True
                and arg.is_array is False
                and arg.default is None
            ):
                raise TODO("arg", "is_required=True", "is_array=False", "default=None")

            if (
                arg.is_required is False
                and arg.is_array is True
                and arg.default is None
            ):
                raise TODO("arg", "is_required=False", "is_array=True", "default=None")

            if (
                arg.is_required is False
                and arg.is_array is False
                and isinstance(arg.default, str)
            ):
                fargs.append(
                    WrapperArgument(
                        id=arg_name,
                        type=str | None,
                        default=repr(arg.default),
                        cond=f"{arg_name} is not None and {arg_name} != {arg.default!r}",
                        argsappend=arg_name,
                    )
                )

            if (
                arg.is_required is False
                and arg.is_array is False
                and arg.default is None
            ):
                raise TODO("arg", "is_required=False", "is_array=False", "default=None")

            if arg.is_required is True and arg.is_array is True and arg.default is None:
                raise TODO("arg", "is_required=True", "is_array=True", "default=None")

        for opt_name, opt in info.definition.options.items():
            opt_name = composer_help_id_to_python_id(opt_name)

            if (
                opt.accept_value is True
                and opt.is_value_required is True
                and opt.is_multiple is False
                and opt.default is None
                or isinstance(opt.default, str)
            ):
                fargs.append(
                    WrapperArgument(
                        id=opt_name,
                        type=str | None if opt.default is None else str,
                        default=repr(opt.default),
                        cond=f"{opt_name} is not None"
                        + (
                            ""
                            if opt.default is None
                            else f" and {opt_name} != {opt.default!r}"
                        ),
                        argsappend=f"{opt.name}={{{opt_name}}}",
                    )
                )

            if (
                opt.accept_value is True
                and opt.is_value_required is True
                and opt.is_multiple is True
                and opt.default is None
            ):
                raise TODO(
                    "opt",
                    "accept_value=True",
                    "is_value_required=True",
                    "is_multiple=True",
                    "default=None",
                    *opt.__dict__.items(),
                )

            if (
                opt.accept_value is True
                and opt.is_value_required is False
                and opt.is_multiple is False
                and opt.default is False
            ):
                raise TODO(
                    "opt",
                    "accept_value=True",
                    "is_value_required=False",
                    "is_multiple=False",
                    "default=False",
                    *opt.__dict__.items(),
                )

            if (
                opt.accept_value is False
                and opt.is_value_required is False
                and opt.is_multiple is False
                and (opt.default is None or isinstance(opt.default, bool))
            ):
                fargs.append(
                    WrapperArgument(
                        id=opt_name,
                        type=bool,
                        default=opt.default,
                        cond=f"not {opt_name}" if opt.default else opt_name,
                        argsappend=opt.name,
                    )
                )

        indent = " " * 4
        flines = []
        flines.append(f"def {fname}(")
        for a in fargs:
            flines.append(
                indent
                + a.id
                + " : "
                + getattr(a.type, "__name__", str(a.type))
                + " = "
                + str(a.default)
                + ","
            )
        flines.append("):")
        flines.append(indent + repr(info.description))
        flines.append("")
        flines.append(indent + "args = []")

        for a in fargs:
            if a.cond:
                flines.append(indent + "if " + a.cond + ":")
                if a.argsappend:
                    flines.append(
                        indent + indent + "args.append(f'" + a.argsappend + "')"
                    )
                else:
                    flines.append(indent + indent + "pass")
            else:
                flines.append(indent + f"# no cond for {a}")

        raise TODO(*flines)

        fdef = ast.FunctionDef(
            name=fname,
            args=ast.arguments(
                posonlyargs=list_of_posonlyargs_from_definition,
                args=list_of_args_from_definition,
                kwonlyargs=list_of_kwonlyargs_from_definition,
                vararg=single_arg_node_referring_to_splat_args,
                kwarg=single_arg_node_referring_to_splat_splat_kwargs,
                kw_defaults=list_of_default_values_for_keyword_only_arguments,
                defaults=list_of_default_values_for_arguments_that_can_be_passed_positionally,
            ),
            body=fbody,
            decorator_list=[],
            returns=ast.Constant(value=None),
            type_params=[],
        )
        m = ast.Module(
            body=[fdef],
            type_ignores=[],
        )
        ast.fix_missing_locations(m)
        (scratch_dir / f"{info.name}.ast.txt").write_text(ast.dump(m, indent=4))
        src = ast.unparse(m)
        formatted_src = black.format_str(src, mode=black.Mode())
        (scratch_dir / f"{fname}.py").write_text(formatted_src)

        # print(formatted_src)


class TODO(NotImplementedError): ...


if __name__ == "__main__":
    frustra.cmds.meighn(composer_help_to_python_function)
