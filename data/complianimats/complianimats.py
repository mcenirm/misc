from __future__ import annotations

from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from csv import writer
from itertools import product
from sys import stderr, stdout
from typing import Any, Mapping, Sequence, TextIO, Type

from yaml import safe_load
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode
from yaml.representer import Representer

SIMPLE_NAME_FOR_YAML_NODE_TYPE: dict[Type[Node], str] = {
    MappingNode: "mapping",
    ScalarNode: "scalar",
    SequenceNode: "sequence",
}


def complianimats(data: TextIO, out: TextIO, /) -> None:
    d = safe_load(data)
    assert isinstance(
        d, Mapping
    ), _get_assertion_message_unexpected_yaml_node_type_for_object(
        "top-level", MappingNode, d
    )
    facets = d.get("facets")
    assert facets is not None, _get_assertion_message_missing_yaml_node("'facets'")
    assert isinstance(
        facets, Mapping
    ), _get_assertion_message_unexpected_yaml_node_type_for_object(
        "'facets'", MappingNode, facets
    )
    for facet_name, facet_list in facets.items():
        assert isinstance(
            facet_list, Sequence
        ), _get_assertion_message_unexpected_yaml_node_type_for_object(
            f"facet[{facet_name!r}]", SequenceNode, facet_list
        )
    w = writer(out)
    w.writerow(facets.keys())
    valuemap = {True: "Yes", False: "No"}
    w.writerows(
        [
            [valuemap.get(value, value) for value in row]
            for row in product(*facets.values())
        ]
    )


def parser(**kwargs) -> ArgumentParser:
    formatter_class = kwargs.pop("formatter_class", ArgumentDefaultsHelpFormatter)
    p = ArgumentParser(formatter_class=formatter_class, **kwargs)
    p.add_argument("data", nargs="?", default="example.yaml", help="input data file")
    return p


def main() -> None:
    args = parser().parse_args()
    try:
        with open(args.data) as data:
            complianimats(data, stdout)
    except AssertionError as e:
        print(str(e), f"(data file: {args.data!r})", file=stderr)
    except FileNotFoundError as e:
        print(str(e), file=stderr)


def _get_assertion_message_missing_yaml_node(label: str) -> str:
    return f"Missing node {label}"


def _get_assertion_message_unexpected_yaml_node_type_for_object(
    label: str,
    expected_node_type: Node,
    actual_object: Any,
) -> str:
    return ", ".join(
        [
            f"For {label}",
            f"expected {SIMPLE_NAME_FOR_YAML_NODE_TYPE[expected_node_type]}",
            f"got {_get_simple_type_name_for_yaml_node_for_object(actual_object)}",
        ]
    )


def _get_yaml_node_for_object(obj: Any) -> Node:
    return Representer().represent_data(obj)


def _get_simple_type_name_for_yaml_node(node: Node) -> str:
    node_type = type(node)
    name = SIMPLE_NAME_FOR_YAML_NODE_TYPE.get(node_type)
    if name:
        return name
    name = node_type.__name__
    name = name.split(".")[-1]
    return name


def _get_simple_type_name_for_yaml_node_for_object(obj: Any) -> str:
    return _get_simple_type_name_for_yaml_node(_get_yaml_node_for_object(obj))


if __name__ == "__main__":
    main()
