import ast
import dataclasses
import json
import subprocess

import dacite

import frustra.cmds


@dataclasses.dataclass
class ComposerHelpArgument:
    default: str
    description: str
    is_array: bool
    is_required: bool
    name: str


@dataclasses.dataclass
class ComposerHelpOption:
    accept_value: bool
    default: bool | str | None
    description: str
    is_multiple: bool
    is_value_required: bool
    name: str
    shortcut: str


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

    print(f"{info.description=}")
    print(f"{info.usage=}")
    print(f"{info.help=}")
    print(f"{info.definition=}")
    print(f"{info.hidden=}")
    fargs = ast.arguments(
        posonlyargs=[posonlyargs_from_definition],
        args=[args_from_definition],
        kwonlyargs=[kwonlyargs_from_definition],
        vararg=single_arg_node_referring_to_splat_args,
        kwarg=single_arg_node_referring_to_splat_splat_kwargs,
        kw_defaults=[default_values_for_keyword_only_arguments],
        defaults=[default_values_for_arguments_that_can_be_passed_positionally],
    )
    fbody = [...]
    fdef = ast.FunctionDef(
        name=f"composer_{info.name}",
        args=fargs,
        body=fbody,
        decorator_list=[],
        returns=ast.Constant(value=None),
        type_params=[],
    )
    m = ast.Module(
        body=[fdef],
        type_ignores=[],
    )
    src = ast.unparse(m)
    print(src)


class TODO(NotImplementedError): ...


if __name__ == "__main__":
    frustra.cmds.meighn(composer_help_to_python_function)
