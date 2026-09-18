import ast
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


@dataclasses.dataclass
class ComposerApplication:
    name: str
    version: str


@dataclasses.dataclass
class ComposerNamespace:
    id: str
    commands: list[str]


@dataclasses.dataclass
class ComposerCommandArgument:
    name: str
    is_required: bool
    is_array: bool
    description: str
    default: str | None


@dataclasses.dataclass
class ComposerCommandOption:
    name: str
    shortcut: str
    accept_value: bool
    is_value_required: bool
    is_multiple: bool
    description: str
    default: bool | str | list[bool] | None


@dataclasses.dataclass
class ComposerCommandDefinition:
    arguments: dict[str, ComposerCommandArgument]
    options: dict[str, ComposerCommandOption]


@dataclasses.dataclass
class ComposerCommand:
    name: str
    description: str
    usage: list[str]
    help: str
    definition: ComposerCommandDefinition
    hidden: bool


@dataclasses.dataclass
class ComposerListOutput:
    application: ComposerApplication
    commands: list[ComposerCommand]
    namespaces: list[ComposerNamespace]


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
                str: lambda v: None if v == [] else v,
                dict[str, ComposerCommandArgument]: lambda v: {} if v == [] else v,
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
        list_of_posonlyargs_from_definition = list()
        list_of_args_from_definition = list()
        list_of_kwonlyargs_from_definition = list()
        single_arg_node_referring_to_splat_args = None
        single_arg_node_referring_to_splat_splat_kwargs = None
        list_of_default_values_for_keyword_only_arguments = list()
        list_of_default_values_for_arguments_that_can_be_passed_positionally = list()
        fbody = list()

        fbody.append(ast.Expr(value=ast.Constant(value=info.description)))

        for arg_name, arg in info.definition.arguments.items():
            arg_name = composer_help_id_to_python_id(arg_name)
            if arg.is_array:
                raise TODO("arg is array", arg_name, *arg.__dict__.items())
            if arg.is_required:
                raise TODO("arg is required", arg_name, *arg.__dict__.items())
            else:
                arg_annotation = ast.BinOp(
                    left=ast.Name(id="str"),
                    op=ast.BitOr(),
                    right=ast.Constant(value=None),
                )
            list_of_args_from_definition.append(
                ast.arg(
                    arg=composer_help_id_to_python_id(arg_name),
                    annotation=arg_annotation,
                )
            )
            list_of_default_values_for_arguments_that_can_be_passed_positionally.append(
                ast.Constant(value=arg.default)
            )
            fbody.append(
                ast.If(
                    test=ast.UnaryOp(
                        op=ast.Not(),
                        operand=ast.Call(
                            func=ast.Name(id="isinstance"),
                            args=[
                                ast.Name(id=arg_name),
                                ast.Name(id="str"),
                            ],
                        ),
                    ),
                    body=[
                        ast.Raise(
                            exc=ast.Call(
                                func=ast.Name(id="TypeError"),
                                args=[
                                    ast.Constant(value=f"{arg_name} should be str"),
                                    ast.Name(id=arg_name),
                                ],
                            )
                        )
                    ],
                )
            )

        fbody.append(
            ast.Assign(
                targets=[
                    ast.Name(
                        id="args",
                        ctx=ast.Store(),
                    )
                ],
                value=ast.List(),
            )
        )

        for opt_name, opt in info.definition.options.items():
            opt_name = composer_help_id_to_python_id(opt_name)
            if opt.accept_value ^ opt.is_value_required:
                raise TODO(
                    "option accept_value and is_value_required do not match",
                    opt_name,
                    *opt.__dict__.items(),
                )
            opt_default = None
            if opt.accept_value:
                opt_value_type = str
            else:
                opt_value_type = bool
                opt_default = False
            if opt_default is None:
                opt_default = opt.default
            arg_annotation = ast.Name(id=opt_value_type.__name__)
            if opt.is_multiple:
                arg_annotation = ast.Subscript(
                    value=ast.Name(id="list"), slice=arg_annotation
                )
            list_of_kwonlyargs_from_definition.append(
                ast.arg(arg=opt_name, annotation=arg_annotation)
            )
            list_of_default_values_for_keyword_only_arguments.append(
                ast.Constant(value=opt_default)
            )
            fbody.append(ast.Expr(value=ast.Constant(value=opt_name)))

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
