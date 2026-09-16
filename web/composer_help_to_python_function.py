import ast
import dataclasses
import json
import subprocess

import black
import dacite
import frustra.cmds
import frustra.strings


@dataclasses.dataclass
class ComposerHelpArgument:
    name: str
    is_required: bool
    is_array: bool
    description: str
    default: str | None


@dataclasses.dataclass
class ComposerHelpOption:
    name: str
    shortcut: str
    accept_value: bool
    is_value_required: bool
    is_multiple: bool
    description: str
    default: bool | str | list[bool] | None


@dataclasses.dataclass
class ComposerHelpDefinition:
    arguments: dict[str, ComposerHelpArgument]
    options: dict[str, ComposerHelpOption]


@dataclasses.dataclass
class ComposerHelpInfo:
    name: str
    description: str
    usage: list[str]
    help: str
    definition: ComposerHelpDefinition
    hidden: bool


def composer_help_id_to_python_id(id: str, prefix: str = "") -> str:
    return frustra.strings.snake_case(prefix + id)


def composer_help_to_python_function(command_name: str):
    jsontext = subprocess.check_output(
        [
            "composer",
            "help",
            command_name,
            "--format=json",
        ],
        universal_newlines=True,
    )
    data = json.loads(jsontext)
    info = dacite.from_dict(
        ComposerHelpInfo,
        data,
        config=dacite.Config(strict=True),
    )

    fname = composer_help_id_to_python_id(info.name, "composer-")
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
        fbody.append(ast.Expr(value=ast.Constant(value=arg_name)))

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
    src = ast.unparse(m)
    formatted_src = black.format_str(src, mode=black.Mode())
    print(formatted_src)


class TODO(NotImplementedError): ...


if __name__ == "__main__":
    frustra.cmds.meighn(composer_help_to_python_function)
