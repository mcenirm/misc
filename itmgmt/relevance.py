"""
https://help.hcltechsw.com/bigfix/9.2/platform/Platform/Relevance/c_relevance_overview.html
"""

from __future__ import annotations

import abc as _abc
import dataclasses as _dataclasses
import enum as _enum
import typing as _typing

from icecream import ic
from rich import inspect as ri


@_dataclasses.dataclass(kw_only=True, frozen=True)
class Effect:
    text: str

    @classmethod
    def from_effect_text(cls, text: str) -> Effect:
        from re import match

        if m := match(
            "Equivalent to the \N{LEFT SINGLE QUOTATION MARK}(.*)\N{RIGHT SINGLE QUOTATION MARK} keyword.",
            text,
        ):
            ic(m)
        return Effect(text=text)


class GrammaticValue(str, _enum.Enum):
    collection = ";"
    division = "/"
    exists = "exists"
    it = "it"
    ite_else = "else"
    ite_if = "if"
    ite_then = "then"
    logical_and = "and"
    logical_or = "or"
    mod = "mod"
    multiplication = "*"
    not_exists = "not exists"
    of = "of"
    phrase = "phrase"
    readability = "<none>"
    relation = "relation"
    string_concatenation = "&"
    subtraction = "-"
    sum = "+"
    tuple = ","
    typecast = "as"
    whose = "whose"


class Token(_enum.Enum):
    a = (
        "a",
        GrammaticValue.readability,
        "Ignored by the relevance evaluator. Used to improve readability.",
    )
    an = (
        "an",
        GrammaticValue.readability,
        "Ignored by the relevance evaluator. Used to improve readability.",
    )
    and_ = (
        "and",
        GrammaticValue.logical_and,
        "The logical AND operator. Doesn\N{RIGHT SINGLE QUOTATION MARK}t evaluate the right hand side if the left hand side is false.",
    )
    collection_operator = (
        ";",
        GrammaticValue.collection,
        "The collection operator. Collects its operands into one plural result.",
    )
    contains = (
        "contains",
        GrammaticValue.relation,
        "Returns TRUE when a string contains another string as a substring.",
    )
    division_operator = (
        "/",
        GrammaticValue.division,
        "The division operator.",
    )
    does_not_contain = (
        "does not contain",
        GrammaticValue.relation,
        "Equivalent to \N{LEFT SINGLE QUOTATION MARK}not contains\N{RIGHT SINGLE QUOTATION MARK}.",
    )
    does_not_end_with = (
        "does not end with",
        GrammaticValue.relation,
        "Returns TRUE when a string does not end with the specified substring.",
    )
    does_not_equal = (
        "does not equal",
        GrammaticValue.relation,
        "Equivalent to \N{LEFT SINGLE QUOTATION MARK}is not\N{RIGHT SINGLE QUOTATION MARK}.",
    )
    does_not_start_with = (
        "does not start with",
        GrammaticValue.relation,
        "Returns TRUE when a string does not start with the specified substring.",
    )
    else_ = (
        "else",
        GrammaticValue.ite_else,
        "Denotes the alternative path in an \N{LEFT SINGLE QUOTATION MARK}if-then-else\N{RIGHT SINGLE QUOTATION MARK} statement.",
    )
    ends_with = (
        "ends with",
        GrammaticValue.relation,
        "Returns TRUE when a string ends with the specified substring.",
    )
    equals = (
        "equals",
        GrammaticValue.relation,
        "Equivalent to \N{LEFT SINGLE QUOTATION MARK}is\N{RIGHT SINGLE QUOTATION MARK}.",
    )
    equals_operator = (
        "=",
        GrammaticValue.relation,
        "Equivalent to the \N{LEFT SINGLE QUOTATION MARK}is\N{RIGHT SINGLE QUOTATION MARK} keyword.",
    )
    exist = (
        "exist",
        GrammaticValue.exists,
        "Returns a boolean TRUE / FALSE indicating whether an object exists.",
    )
    exist_no = (
        "exist no",
        GrammaticValue.not_exists,
        "Equivalent to \N{LEFT SINGLE QUOTATION MARK}not exist\N{RIGHT SINGLE QUOTATION MARK}.",
    )
    exists = (
        "exists",
        GrammaticValue.exists,
        "Equivalent to \N{LEFT SINGLE QUOTATION MARK}exist\N{RIGHT SINGLE QUOTATION MARK}.",
    )
    exists_no = (
        "exists no",
        GrammaticValue.not_exists,
        "Equivalent to \N{LEFT SINGLE QUOTATION MARK}not exist\N{RIGHT SINGLE QUOTATION MARK}.",
    )
    greater_than_operator = (
        ">",
        GrammaticValue.relation,
        "The \N{LEFT SINGLE QUOTATION MARK}greater than\N{RIGHT SINGLE QUOTATION MARK} operator.",
    )
    greater_than_or_equal_to_operator = (
        ">=",
        GrammaticValue.relation,
        "The \N{LEFT SINGLE QUOTATION MARK}greater than or equal to\N{RIGHT SINGLE QUOTATION MARK} operator.",
    )
    if_ = (
        "if",
        GrammaticValue.ite_if,
        "The keyword to begin an \N{LEFT SINGLE QUOTATION MARK}if-then-else\N{RIGHT SINGLE QUOTATION MARK} expression.",
    )
    is_ = (
        "is",
        GrammaticValue.relation,
        "Returns TRUE when two objects are equal. Note that not all objects can be tested for equality. Equivalent to the \N{LEFT SINGLE QUOTATION MARK}=\N{RIGHT SINGLE QUOTATION MARK} operator.",
    )
    is_contained_by = (
        "is contained by",
        GrammaticValue.relation,
        "Returns TRUE when a string contains another string as a substring.",
    )
    is_equal_to = (
        "is equal to",
        GrammaticValue.relation,
        "Equivalent to \N{LEFT SINGLE QUOTATION MARK}is\N{RIGHT SINGLE QUOTATION MARK}.",
    )
    is_greater_than = (
        "is greater than",
        GrammaticValue.relation,
        "The \N{LEFT SINGLE QUOTATION MARK}>\N{RIGHT SINGLE QUOTATION MARK} comparison.",
    )
    is_greater_than_or_equal_to = (
        "is greater than or equal to",
        GrammaticValue.relation,
        "The \N{LEFT SINGLE QUOTATION MARK}>=\N{RIGHT SINGLE QUOTATION MARK} comparison.",
    )
    is_less_than_ = (
        "is less than",
        GrammaticValue.relation,
        "The \N{LEFT SINGLE QUOTATION MARK}<\N{RIGHT SINGLE QUOTATION MARK} comparison.",
    )
    is_less_than_or_equal_to = (
        "is less than or equal to",
        GrammaticValue.relation,
        "The \N{LEFT SINGLE QUOTATION MARK}<=\N{RIGHT SINGLE QUOTATION MARK} comparison.",
    )
    is_not = (
        "is not",
        GrammaticValue.relation,
        "Returns TRUE when two objects are not equal. Note that not all objects can be compared with this keyword.",
    )
    is_not_contained_by = (
        "is not contained by",
        GrammaticValue.relation,
        "Returns TRUE when a string does not contain another string as a substring.",
    )
    is_not_equal_to = (
        "is not equal to",
        GrammaticValue.relation,
        "Equivalent to the keyword \N{LEFT SINGLE QUOTATION MARK}is not\N{RIGHT SINGLE QUOTATION MARK} and the \N{LEFT SINGLE QUOTATION MARK}!=\N{RIGHT SINGLE QUOTATION MARK} operator.",
    )
    is_not_greater_than = (
        "is not greater than",
        GrammaticValue.relation,
        "Equivalent to is less than or equal to or \N{LEFT SINGLE QUOTATION MARK}<=\N{RIGHT SINGLE QUOTATION MARK}.",
    )
    is_not_greater_than_or_equal_to = (
        "is not greater than or equal to",
        GrammaticValue.relation,
        "Equivalent to is less than or \N{LEFT SINGLE QUOTATION MARK}<\N{RIGHT SINGLE QUOTATION MARK}.",
    )
    is_not_less_than = (
        "is not less than",
        GrammaticValue.relation,
        "Equivalent to is greater than or equal to or \N{LEFT SINGLE QUOTATION MARK}>=\N{RIGHT SINGLE QUOTATION MARK}.",
    )
    is_not_less_than_or_equal_to = (
        "is not less than or equal to",
        GrammaticValue.relation,
        "Equivalent to is greater than or \N{LEFT SINGLE QUOTATION MARK}>\N{RIGHT SINGLE QUOTATION MARK}.",
    )
    it = (
        "it",
        GrammaticValue.it,
        "A reference to the closest direct object or \N{LEFT SINGLE QUOTATION MARK}whose\N{RIGHT SINGLE QUOTATION MARK} clause.",
    )
    item = (
        "item",
        GrammaticValue.phrase,
        "Used to index into a tuple. Always returns a singular value.",
    )
    items = (
        "items",
        GrammaticValue.phrase,
        "Equivalent to item, but returns a plural value.",
    )
    less_than_operator = (
        "<",
        GrammaticValue.relation,
        "The \N{LEFT SINGLE QUOTATION MARK}less than\N{RIGHT SINGLE QUOTATION MARK} operator.",
    )
    less_than_or_equal_to_operator = (
        "<=",
        GrammaticValue.relation,
        "The \N{LEFT SINGLE QUOTATION MARK}less than or equal to\N{RIGHT SINGLE QUOTATION MARK} operator.",
    )
    mod = (
        "mod",
        GrammaticValue.mod,
        "The modulo operator.",
    )
    multiplication_operator = (
        "*",
        GrammaticValue.multiplication,
        "The multiplication operator.",
    )
    not_ = (
        "not",
        GrammaticValue.relation,
        "The logical NOT operator.",
    )
    not_equals_operator = (
        "!=",
        GrammaticValue.relation,
        "Equivalent to \N{LEFT SINGLE QUOTATION MARK}is not\N{RIGHT SINGLE QUOTATION MARK}.",
    )
    number = (
        "number",
        GrammaticValue.phrase,
        "Returns the number of results in an expression.",
    )
    of = (
        "of",
        GrammaticValue.of,
        "Used to access a property of an object.",
    )
    or_ = (
        "or",
        GrammaticValue.logical_or,
        "The logical OR operator. Doesn\N{RIGHT SINGLE QUOTATION MARK}t evaluate the right hand side if the left hand side is true.",
    )
    starts_with = (
        "starts with",
        GrammaticValue.relation,
        "Returns TRUE when a string begins with the specified substring.",
    )
    string_concatenation_operator = (
        "&",
        GrammaticValue.string_concatenation,
        "The string concatenation operator.",
    )
    subtraction_operator = (
        "-",
        GrammaticValue.subtraction,
        "The subtraction operator.",
    )
    sum_operator = (
        "+",
        GrammaticValue.sum,
        "The sum operator.",
    )
    the = (
        "the",
        GrammaticValue.readability,
        "Ignored by the relevance evaluator. Used to improve readability.",
    )
    then = (
        "then",
        GrammaticValue.ite_then,
        "Denotes the main path to take in an if-then-else expression.",
    )
    there_do_not_exist = (
        "there do not exist",
        GrammaticValue.not_exists,
        "Equivalent to \N{LEFT SINGLE QUOTATION MARK}not exist\N{RIGHT SINGLE QUOTATION MARK}.",
    )
    there_does_not_exist = (
        "there does not exist",
        GrammaticValue.not_exists,
        "Equivalent to \N{LEFT SINGLE QUOTATION MARK}not exist\N{RIGHT SINGLE QUOTATION MARK}.",
    )
    there_exist = (
        "there exist",
        GrammaticValue.exists,
        "Equivalent to \N{LEFT SINGLE QUOTATION MARK}exist\N{RIGHT SINGLE QUOTATION MARK}.",
    )
    there_exist_no = (
        "there exist no",
        GrammaticValue.not_exists,
        "Equivalent to \N{LEFT SINGLE QUOTATION MARK}not exist\N{RIGHT SINGLE QUOTATION MARK}.",
    )
    there_exists = (
        "there exists",
        GrammaticValue.exists,
        "Equivalent to \N{LEFT SINGLE QUOTATION MARK}exist\N{RIGHT SINGLE QUOTATION MARK}.",
    )
    there_exists_no = (
        "there exists no",
        GrammaticValue.not_exists,
        "Equivalent to \N{LEFT SINGLE QUOTATION MARK}not exist\N{RIGHT SINGLE QUOTATION MARK}.",
    )
    tuple_operator = (
        ",",
        GrammaticValue.tuple,
        "The tuple operator. Creates a tuple of objects.",
    )
    typecast_operator = (
        "as",
        GrammaticValue.typecast,
        "The typecast operator, used to convert one type to another.",
    )
    whose = (
        "whose",
        GrammaticValue.whose,
        "Used along with the \N{LEFT SINGLE QUOTATION MARK}it\N{RIGHT SINGLE QUOTATION MARK} keyword to filter plural results.",
    )

    def __new__(
        cls,
        text: str,
        grammatic_value: GrammaticValue,
        effect_text: str,
    ):
        obj = object.__new__(cls)
        obj._value_ = text
        obj.grammatic_value = grammatic_value
        obj.effect = Effect.from_effect_text(effect_text)
        return obj


def run(infile: _typing.TextIO, outfile: _typing.TextIO):
    ...


def main() -> None:
    from sys import stdin, stdout

    run(infile=stdin, outfile=stdout)


def grammar_checklist(
    grammar_csv="relevance-grammar.csv",
    worry_key="Worry",
    associativity_marker="associativity",
    operator_marker="operator",
    keyword_marker="keyword",
    token_key="Token",
    grammatic_value_key="Grammatic Value",
    associativity_key="Associativity",
    description_key="Description",
    effect_key="Effect",
):
    from csv import DictReader
    from inspect import getmembers, isclass
    from sys import modules

    # my_module_name = Token.__module__
    # my_module = modules[my_module_name]
    # my_module_members = getmembers(my_module)
    # my_module_classes = [obj for _, obj in my_module_members if isclass(obj)]
    with open(grammar_csv, encoding="utf-8") as f:
        reader = DictReader(f)
        for row in reader:
            worry = row[worry_key]
            if worry in {operator_marker, keyword_marker}:
                token_text = row[token_key]
                gv_text = row[grammatic_value_key]
                effect_text = row[effect_key]
                try:
                    gv = GrammaticValue(gv_text)
                except ValueError as ve:
                    raise ValueError("Unexpected grammatic value", gv_text, row) from ve
                try:
                    token = Token(token_text)
                except ValueError as ve:
                    raise ValueError("Unexpected token", token_text, row) from ve
            elif worry == associativity_marker:
                # TODO implement checks for associativity
                ...
            else:
                raise ValueError("unexpected worry: " + worry)


def _devmain():
    from doctest import FAIL_FAST, testmod

    testmod(optionflags=FAIL_FAST)
    grammar_checklist()


if __name__ == "__main__":
    _devmain()
    main()
