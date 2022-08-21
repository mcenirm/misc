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
        # from re import match

        # if m := match(
        #     "Equivalent to the \N{LEFT SINGLE QUOTATION MARK}(.*)\N{RIGHT SINGLE QUOTATION MARK} keyword.",
        #     text,
        # ):
        #     ic(m)
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
    left_parentheses = "("
    multiplication = "*"
    not_ = "not"
    not_exists = "not exists"
    of = "of"
    phrase = "phrase"
    readability = "<none>"
    relation = "relation"
    right_parentheses = ")"
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
        obj._grammatic_value = grammatic_value
        obj._effect = Effect.from_effect_text(effect_text)
        return obj

    @property
    def grammatic_value(self) -> GrammaticValue:
        return self._grammatic_value

    @property
    def effect(self) -> Effect:
        return self._effect


class ExtraToken(_enum.Enum):
    left_parenthesis = ("(", GrammaticValue.left_parentheses)
    right_parenthesis = (")", GrammaticValue.right_parentheses)

    def __new__(
        cls,
        text: str,
        grammatic_value: GrammaticValue,
    ):
        obj = object.__new__(cls)
        obj._value_ = text
        obj._grammatic_value = grammatic_value
        return obj

    @property
    def grammatic_value(self) -> GrammaticValue:
        return self._grammatic_value

    @property
    def effect(self) -> Effect:
        return Effect(text="")


class Associativity(_enum.Enum):
    left = "left"


class Rule(_enum.Enum):
    parentheses = (
        "parentheses",
        1,
        {
            GrammaticValue.left_parentheses,
            GrammaticValue.right_parentheses,
        },
    )
    casting_operator = (
        "casting operator",
        2,
        {
            GrammaticValue.typecast,
        },
        Associativity.left,
    )
    unary_operator = (
        "unary operator",
        3,
        {
            GrammaticValue.exists,
            GrammaticValue.not_,
            GrammaticValue.not_exists,
            GrammaticValue.subtraction,
        },
        Associativity.left,
    )
    products = (
        "products",
        4,
        {
            GrammaticValue.string_concatenation,
            GrammaticValue.mod,
            GrammaticValue.multiplication,
            GrammaticValue.division,
        },
        Associativity.left,
    )
    addition = (
        "addition",
        5,
        {
            GrammaticValue.subtraction,
            GrammaticValue.sum,
        },
        Associativity.left,
    )
    relations = (
        "relations",
        6,
        {
            GrammaticValue.relation,
        },
    )
    and_ = (
        "AND",
        7,
        {
            GrammaticValue.logical_and,
        },
        Associativity.left,
    )
    or_ = (
        "OR",
        8,
        {
            GrammaticValue.logical_or,
        },
        Associativity.left,
    )
    tuple = (
        "Tuple",
        9,
        {
            GrammaticValue.tuple,
        },
    )
    plural = (
        "plural",
        10,
        {
            GrammaticValue.collection,
        },
        Associativity.left,
    )

    def __new__(
        cls,
        description: str,
        precedence: int,
        grammatic_values: _typing.Iterable[GrammaticValue],
        associativity: Associativity | None = None,
    ):
        obj = object.__new__(cls)
        obj._value_ = description
        obj._precedence = precedence
        obj._grammatic_values = set(grammatic_values)
        obj._associativity = associativity
        return obj

    @property
    def description(self) -> str:
        return self.value

    @property
    def precedence(self) -> int:
        return self._precedence

    @property
    def grammatic_values(self) -> set[GrammaticValue]:
        return self._grammatic_values

    @property
    def associativity(self) -> Associativity | None:
        return self._associativity

    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.precedence >= other.precedence
        return NotImplemented

    def __gt__(self, other):
        if self.__class__ is other.__class__:
            return self.precedence > other.precedence
        return NotImplemented

    def __le__(self, other):
        if self.__class__ is other.__class__:
            return self.precedence <= other.precedence
        return NotImplemented

    def __lt__(self, other):
        if self.__class__ is other.__class__:
            return self.precedence < other.precedence
        return NotImplemented


class Expression:
    ...


@_dataclasses.dataclass(frozen=True)
class Term:
    original_text: str
    normalized_text: str | None = None
    token: Token | ExtraToken | None = None

    @classmethod
    def from_text(text: str) -> tuple[Term, str]:
        # TODO
        ...


class TermBuilder:
    def __init__(self, first_ch: str, chindex: int, linenum: int, colnum: int) -> None:
        self.chs = [first_ch]
        self.chindexs = [chindex]
        self.linenums = [linenum]
        self.colnums = [colnum]

    def append(self, ch: str, chindex: int, linenum: int, colnum: int) -> TermBuilder:
        self.chs.append(ch)
        self.chindexs.append(chindex)
        self.linenums.append(linenum)
        self.colnums.append(colnum)
        return self

    def resolve(self) -> Term:
        from itertools import chain
        from re import sub

        text = "".join(self.chs)
        normalized_text = sub(r"\s+", " ", text)
        longest_match_token = None
        longest_match_length = 0
        for t in chain(ExtraToken, Token):
            if normalized_text.startswith(t.value):
                if len(t.value) > longest_match_length:
                    longest_match_token = t
                    longest_match_length = len(t.value)
        if longest_match_token:
            return Term(text=text, token=longest_match_token)


class ParseState(_enum.Enum):
    eating_spaces = _enum.auto()
    inside_expression = _enum.auto()
    inside_quotation = _enum.auto()
    # expecting_expression = _enum.auto()
    # identifier_or_keyword = _enum.auto()
    # quoted_escape = _enum.auto()


class StringishStream:
    def __init__(self, f: _typing.TextIO) -> None:
        super().__init__()
        self.f = f
        self.b = f.read(1)
        self.eof = self.b == ""

    def __bool__(self) -> bool:
        return self.eof

    def peek(self) -> str:
        if self.eof:
            return ""
        if not self.b:
            b = self.f.read(1)

        return b[0]


def parse(f: _typing.TextIO):
    from unicodedata import category

    stream = StringishStream(f)
    stack = []
    state = ParseState.expecting_expression
    # chindex = 0
    # linenum = 1
    # colnum = 1
    builder = None
    while stream:
        ch = stream.peek()
        chcat = category(ch)
        match state, chcat, ch:
            case _:
                raise ValueError("panic", state, eof, chcat, ch)
    match state:
        case _:
            raise ValueError("eof panic", state)

    # while ch := f.read(1):
    #     eof = len(ch) < 1
    #     chcat = None if eof else category(ch)
    #     match state, eof, chcat, ch:
    #         case ParseState.expecting_expression, True, _, _:
    #             break
    #         case ParseState.expecting_expression, _, _, ExtraToken.left_parenthesis.value:
    #             stack.append(dict(chindex=chindex, linenum=linenum, colnum=colnum))
    #             state = ParseState.expecting_expression
    #         case ParseState.expecting_expression, _, "Ll", _:
    #             builder = TermBuilder(ch, chindex, linenum, colnum)
    #             state = ParseState.identifier_or_keyword
    #         case ParseState.identifier_or_keyword, _, "Ll" | "Zs", _:
    #             builder.append(ch, chindex, linenum, colnum)
    #             state = ParseState.identifier_or_keyword
    #         case ParseState.identifier_or_keyword, _, _, ExtraToken.right_parenthesis.value:
    #             term = builder.resolve()
    #             builder.append(ch, chindex, linenum, colnum)
    #             state = ParseState.identifier_or_keyword
    #         case _:
    #             raise ValueError("panic", state, eof, chcat, ch)
    #     chindex += len(ch)
    if stack:
        ic(stack)
    if builder:
        ic(builder)


def run(infile: _typing.TextIO, outfile: _typing.TextIO) -> None:
    for expr in parse(infile):
        print(expr.indent(), file=outfile)


class IndentedPrinter:
    def __init__(self, print=print, level=0) -> None:
        self.print = print
        self.level = level
        self.prefix = " " * self.level
        self.need_prefix = True

    def __call__(self, *args, **kwargs):
        if self.need_prefix:
            args = list(args)
            args.insert(0, self.prefix)
        self.need_prefix = kwargs.get("end") is None
        return self.print(*args, **kwargs)


class CountingCharacters:
    def __init__(self, f: _typing.TextIO) -> None:
        self.f = f
        self.c = 0

    def read(self, n: int, /) -> str:
        s = self.f.read(n)
        self.c += len(s)
        return s

    def tell(self) -> int:
        return self.c


def indent(stream: CountingCharacters, print=print, level: int = 0) -> None:
    ip = IndentedPrinter(print, level)
    state = ParseState.eating_spaces
    while ch := stream.read(1):
        where = stream.tell() - 1
        try:
            if state == ParseState.eating_spaces:
                while ch.isspace() and (ch := stream.read(1)):
                    ...
                if ch == ExtraToken.left_parenthesis.value:
                    ip(ExtraToken.left_parenthesis.value)
                    indent(stream, print, level + 1)
                    ip(ExtraToken.right_parenthesis.value)
                elif ch == ExtraToken.right_parenthesis.value:
                    if level:
                        ip()
                        return
                    else:
                        raise ValueError("unexpected right parenthesis")
                elif ch == '"':
                    ip(ch, end="")
                    state = ParseState.inside_quotation
                elif ch.isprintable():
                    ip(ch, end="")
                else:
                    raise ValueError()
            elif state == ParseState.inside_expression:
                if ch == ExtraToken.left_parenthesis.value:
                    ip(ExtraToken.left_parenthesis.value)
                    indent(stream, print, level + 1)
                    ip(ExtraToken.right_parenthesis.value)
                elif ch == ExtraToken.right_parenthesis.value:
                    if level:
                        ip()
                        return
                    else:
                        raise ValueError("unexpected right parenthesis")
                elif ch.isspace():
                    ip(" ", end="")
                    state = ParseState.eating_spaces
                elif ch == '"':
                    ip(ch, end="")
                    state = ParseState.inside_quotation
                elif ch.isprintable():
                    ip(ch, end="")
                else:
                    raise ValueError()
            elif state == ParseState.inside_quotation:
                if ch == '"':
                    ip(ch, end="")
                    state = ParseState.eating_spaces
                elif ch.isprintable():
                    ip(ch, end="")
                else:
                    raise ValueError()
            else:
                raise ValueError("bad state")
        except ValueError as ve:
            raise ValueError("indent", *ve.args, ch, where, state) from ve


def main() -> None:
    from sys import argv, stdin, stdout

    args = argv[1:]
    if args and args[0] == "-i":
        indent(CountingCharacters(stdin))
    else:
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
    precedence_key="Precedence",
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
        unexpected_rules_by_description = dict()
        existing_rule_names_and_gv_names = set(
            [(r.name, g.name) for r in Rule for g in r.grammatic_values]
        )
        loaded_rule_names_and_gv_names = set()
        for row in reader:
            worry = row[worry_key]
            gv_text = row[grammatic_value_key]
            try:
                gv = GrammaticValue(gv_text)
            except ValueError as ve:
                raise ValueError("Unexpected grammatic value", gv_text, row) from ve
            if worry in {operator_marker, keyword_marker}:
                token_text = row[token_key]
                effect_text = row[effect_key]
                try:
                    token = Token(token_text)
                except ValueError as ve:
                    raise ValueError("Unexpected token", token_text, row) from ve
            elif worry == associativity_marker:
                # TODO implement checks for associativity
                desc_text = row[description_key]
                assoc_text = row[associativity_key]
                prec_text = row[precedence_key]
                if not desc_text:
                    raise ValueError("Missing description for associativity", row)
                try:
                    assoc = Associativity(assoc_text) if assoc_text else None
                except ValueError as ve:
                    raise ValueError("Unexpected associativity", assoc_text, row)
                try:
                    rule = Rule(desc_text)
                    loaded_rule_names_and_gv_names.add((rule.name, gv.name))
                except ValueError as ve:
                    if len(Rule):
                        raise ValueError(
                            "Unexpected rule description", desc_text, row
                        ) from ve
                    else:
                        if desc_text not in unexpected_rules_by_description:
                            unexpected_rules_by_description[desc_text] = (
                                desc_text,
                                prec_text,
                                assoc,
                                set(),
                            )
                        unexpected_rules_by_description[desc_text][3].add(gv)
                if rule.precedence != int(prec_text):
                    raise ValueError("Mismatched rule precedence", prec_text, rule, row)
                if rule.associativity != assoc:
                    raise ValueError("Mismatched rule associativity", assoc, rule, row)
                if gv not in rule.grammatic_values:
                    raise ValueError("Mismatched rule grammatic value", gv, rule, row)
            else:
                raise ValueError("unexpected worry: " + worry)
    existing_but_not_loaded_rule_names_and_gv_names = (
        existing_rule_names_and_gv_names.difference(loaded_rule_names_and_gv_names)
    )
    if existing_but_not_loaded_rule_names_and_gv_names:
        print("##  existing but not loaded rule grammatic values ##")
        for rn, gn in existing_but_not_loaded_rule_names_and_gv_names:
            print("#  ", Rule[rn], "->", GrammaticValue[gn])
    if unexpected_rules_by_description:
        print("## add to class Rule ##")
        for (
            desc_text,
            prec_text,
            assoc,
            gvs,
        ) in unexpected_rules_by_description.values():
            args = []
            name = _snake(desc_text)
            from keyword import iskeyword

            if iskeyword(name):
                name += "_"
            args.append(repr(desc_text))
            args.append(prec_text)
            args.append(
                "".join(
                    [
                        "{",
                        ", ".join(
                            [".".join([gv.__class__.__name__, gv.name]) for gv in gvs]
                        ),
                        ",}",
                    ]
                )
            )
            if assoc:
                args.append(".".join([assoc.__class__.__name__, assoc.name]))
            print("   ", name, "=", "".join(["(", ", ".join(args), ",)"]))
        ...


def _snake(s: str) -> str | None:
    from re import sub
    from unicodedata import category, normalize

    if not s:
        return None

    s = normalize("NFC", s)
    chs = []
    pch = s[0]
    pchcat = category(pch)
    if pch.islower() or pch.isnumeric():
        chs.append(pch)
    elif pch.isupper():
        chs.append(pch.lower())
    for ch in s[1:]:
        chcat = category(ch)
        match list(pchcat + chcat):
            case ["L" | "N" | "P" | "Z", _, "L", "l"] | ["L" | "N" | "P", _, "N", "d"]:
                chs.append(ch)
            case ["P" | "S" | "Z", _, "P" | "S", _]:
                pass
            case ["L" | "N" | "P" | "S" | "Z", _, "P" | "S" | "Z", _]:
                chs.append(" ")
            case ["L", "l", "L", "u"] | ["N", "d", "L", "u"]:
                chs.append(" ")
                chs.append(ch.lower())
            case ["L", "u", "L", "u"] | ["P" | "S" | "Z", _, "L", "u"]:
                chs.append(ch.lower())
            case _:
                raise ValueError("Unhandled", pchcat, chcat)
        pch = ch
        pchcat = chcat
    if not chs:
        return None
    s = "".join(chs)
    s = s.strip()
    s = sub(r"\s+", "_", s)
    return s


def _devmain():
    from doctest import FAIL_FAST, testmod

    testmod(optionflags=FAIL_FAST)
    grammar_checklist()


if __name__ == "__main__":
    _devmain()
    main()
