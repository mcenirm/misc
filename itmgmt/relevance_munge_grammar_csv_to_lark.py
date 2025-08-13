from __future__ import annotations

import collections
import collections.abc
import csv
import dataclasses
import functools
import inspect
import keyword
import operator
import pathlib
import re
import sys
import typing
import unicodedata

from frustra.agenda import ActionItems
from frustra.conlecta import (
    AdHocEquivalenceClasses,
    NoClobberDict,
    defaultdict_where_default_value_is_missing_key,
    defaultdict_where_factory_takes_missing_key_as_arg,
)
from frustra.csvs import open_file_for_csv_reader
from frustra.dump import dump
from frustra.strings import CONSTANT_CASE, repr_str_with_double_quotes, snake_case
from frustra.typicals import trycast


def relevance_munge_grammar_csv_to_lark(
    csvfilename: str | pathlib.Path, larkfilename: str | pathlib.Path
):
    rows = read_relevance_grammar_csv(csvfilename)
    grammar = RG(rows)
    larkfilename = pathlib.Path(larkfilename)
    with larkfilename.open("w", encoding="utf-8") as out:
        writer = RGWriter(
            grammar,
            lark_module_name="." + larkfilename.stem,
            print=functools.partial(print, file=out),
        )
        writer.write_grammar()


WORRIES_TO_IGNORE = {"pseudokeyword"}

RG_WORRY = "worry"
RG_TOKEN = "token"
RG_GRAMMATIC_VALUE = "grammatic_value"
RG_ORIGINAL_GV = "original_gv"
RG_ASSOCIATIVITY = "associativity"
RG_DESCRIPTION = "description"
RG_PRECEDENCE = "precedence"
RG_EFFECT = "effect"

RG_TOK_NOT_EQUAL = "!="
RG_TOK_LEFT_PARENTHESIS = "("
RG_TOK_RIGHT_PARENTHESIS = ")"

RG_DESC_PARENTHESES = "parentheses"
RG_DESC_UNARY_OPERATOR = "unary operator"

RG_ASSOC_LEFT = "left"

LARK_START_RULE_NAME = "expr"
LARK_VALUE_RULE_NAME = "value"


class RG:
    def __init__(self, rows: list[RowType]):
        self._standin_tokens_by_tok: collections.abc.MutableMapping[
            str, _standin_RGToken
        ] = defaultdict_where_factory_takes_missing_key_as_arg(_standin_RGToken)
        self._standin_exprs_by_gv: dict[str, list[_standin_RGExpression]] = (
            collections.defaultdict(list)
        )
        self._standin_exprs_by_prec: dict[float, list[_standin_RGExpression]] = (
            collections.defaultdict(list)
        )
        self._standin_exprs_by_desc: dict[str, list[_standin_RGExpression]] = (
            collections.defaultdict(list)
        )
        self._prepare_standins(rows)

        self._tok_equivalence_classes: dict[str, set[str]] = {}
        self._eqtoks_by_tok: dict[str, set[str]] = {}
        self._unexpected_eqtoks: set[str] = set()
        self._build_out_token_equivalence_classes()

        # self._opnames_by_tok: dict[str, str] = NoClobberDict()
        # self._tokens: list[RGToken] = []
        self._token_by_tok: dict[str, RGToken] = NoClobberDict()
        self._token_by_name: dict[str, RGToken] = NoClobberDict()
        self._tokens_by_gv: dict[str, list[RGToken]] = collections.defaultdict(list)
        self._token_group_by_tok: dict[str, RGEquivalentTokensGroup] = NoClobberDict()
        self._token_group_by_name: dict[str, RGEquivalentTokensGroup] = NoClobberDict()
        self._expressions_by_prec: dict[float, RGExpression] = NoClobberDict()
        self._expressions_by_desc: dict[str, RGExpression] = NoClobberDict()
        # self._exprs: list[RGExpression] = []
        # self._groups: list[RGEquivalentTokensGroup] = []
        self._create_tokens_and_expressions()

    def _prepare_standins(self, rows: list[RowType]):
        rows = [r.copy() for r in rows]
        # foo = NoClobberDict()
        # for row in rows:
        #     gv = row[RG_GRAMMATIC_VALUE]
        #     tok = row[RG_TOKEN]
        #     desc = row.get(RG_DESCRIPTION)
        #     eff = row.get(RG_EFFECT)
        #     foo[(gv, desc)] = row
        #     if eff:
        #         foo[(tok, eff)] = row
        self._prepare_standin_tokens(rows)
        self._prepare_standin_expressions(rows)

    def _prepare_standin_tokens(self, rows: list[RowType]):
        for row in rows:
            wry = row[RG_WORRY]
            tok = row[RG_TOKEN]
            gv = row[RG_GRAMMATIC_VALUE]
            assoc = row.get(RG_ASSOCIATIVITY)
            desc = row.get(RG_DESCRIPTION)
            prec = row.get(RG_PRECEDENCE)
            eff = row.get(RG_EFFECT)

            sit = self._standin_tokens_by_tok[typing.cast(str, tok)]
            sit.gvs.add(typing.cast(str, gv))
            sit.eff = typing.cast(str, eff)

        self._guess_token_priorities_for_lexer()
        self._guess_opnames_for_tokens()

    def _prepare_standin_expressions(self, rows: list[RowType]):
        for row in rows:
            wry = row[RG_WORRY]
            tok = row[RG_TOKEN]
            gv = row[RG_GRAMMATIC_VALUE]
            assoc = row.get(RG_ASSOCIATIVITY)
            desc = row.get(RG_DESCRIPTION)
            prec = row.get(RG_PRECEDENCE)
            eff = row.get(RG_EFFECT)
            if prec is not None:
                sie = _standin_RGExpression(
                    gv=typing.cast(str, gv),
                    prec=typing.cast(float, prec),
                    tok=typing.cast(str, tok),
                    desc=typing.cast(str, desc),
                    left_assoc=assoc == RG_ASSOC_LEFT,
                )
                self._standin_exprs_by_gv[sie.gv].append(sie)
                self._standin_exprs_by_prec[sie.prec].append(sie)
                self._standin_exprs_by_desc[sie.desc].append(sie)

    def _guess_token_priorities_for_lexer(self):
        for tok1, sit1 in self._standin_tokens_by_tok.items():
            for tok2 in self._standin_tokens_by_tok:
                if tok1.startswith(tok2):
                    sit1.prio += 1

    def _guess_opnames_for_tokens(self):
        for sit in self._standin_tokens_by_tok.values():
            if sit.eff is not None:
                if sit.opname is not None:
                    raise ValueError("opname already set", dict(standintoken=sit))
                for pat in [
                    r"The ‘([^.]+)’ operator\.",
                    r"The ([^.]+) operator[.,]",
                ]:
                    m_opname = re.search(pat, sit.eff)
                    if m_opname:
                        sit.opname = m_opname.group(1)
                        break

    def _build_out_token_equivalence_classes(self):
        ahec = AdHocEquivalenceClasses()
        self._unexpected_eqtoks = set()
        for sit in self._standin_tokens_by_tok.values():
            ahec.equate(sit.tok)
            if sit.eff is not None:
                for pat in [
                    r"Equivalent to the ‘([^.]+)’ (keyword|operator)\.",
                    r"Equivalent to ‘([^.]+)’",
                    r"The ‘([^.]+)’ comparison.",
                    r"Equivalent to the keyword ‘([^.]+)’ and the ‘[^.]+’ operator.",
                    r"Equivalent to the keyword ‘[^.]+’ and the ‘([^.]+)’ operator.",
                    r"Equivalent to ([^.]+) or ‘[^.]+’.",
                    r"Equivalent to [^.]+ or ‘([^.]+)’.",
                ]:
                    m_equiv = re.search(pat, sit.eff)
                    if m_equiv:
                        eqtok = m_equiv.group(1)
                        if eqtok not in self._standin_tokens_by_tok:
                            for gv in sit.gvs:
                                if gv in self._standin_tokens_by_tok:
                                    eqtok = gv
                                    sit.found_eqtok = True
                            else:
                                self._unexpected_eqtoks.add(eqtok)
                        if eqtok in self._standin_tokens_by_tok:
                            ahec.equate(sit.tok, eqtok)
                            sit.found_eqtok = True
        self._tok_equivalence_classes = ahec.get_equivalence_classes()
        self._eqtoks_by_tok = NoClobberDict()
        for tok in self._standin_tokens_by_tok:
            eqtoks = ahec.get_equivalence_class(tok)
            if eqtoks:
                self._eqtoks_by_tok[tok] = eqtoks
            else:
                ValueError("tok has no eqtoks", dict(tok=tok))

    def _create_tokens_and_expressions(self):
        self._create_tokens()
        self._create_token_groups()
        self._create_expressions()

    def _create_tokens(self):
        for sit in self._standin_tokens_by_tok.values():
            self._guess_name_for_standin_token(sit)
            token = sit.as_token()
            self._token_by_tok[token.tok] = token
            self._token_by_name[token.name] = token
            for gv in sit.gvs:
                self._tokens_by_gv[gv].append(token)

    def _create_token_groups(self):
        for reptok, othertokens in self._tok_equivalence_classes.items():
            othertokens = [tok for tok in othertokens if tok != reptok]
            reptoken = self._token_by_tok[reptok]
            othertokens = [
                self._token_by_tok[tok] for tok in othertokens if tok != reptok
            ]
            namesake = reptoken
            for othertoken in othertokens:
                if len(othertoken.name) < len(namesake.name):
                    namesake = othertoken
            group = RGEquivalentTokensGroup(
                namesake=namesake,
                tokens=set([reptoken, *othertokens]),
            )
            self._token_group_by_name[group.name] = group
            for token in group.tokens:
                self._token_group_by_tok[token.tok] = group

    def _create_expressions(self):
        def _check_singular[_T](
            name: str, typ: type[_T], prec: float, sies: list[_standin_RGExpression]
        ) -> _T:
            values: set[_T] = {getattr(sie, name) for sie in sies}
            if len(values) != 1:
                raise ValueError(
                    f"non-singular {name} for prec",
                    {"prec": prec, "sies": sies, name: values},
                )
            return next(iter(values))

        preceding_expr = None
        for prec, sies in sorted(self._standin_exprs_by_prec.items()):
            desc = _check_singular("desc", str, prec, sies)
            left_assoc = _check_singular("left_assoc", bool, prec, sies)
            tokengroups = [self._token_group_by_tok[sie.tok] for sie in sies]
            expr = RGExpression(
                prec=prec,
                desc=desc,
                left_assoc=left_assoc,
                preceding_expr=preceding_expr,
                tokengroups=tokengroups,
            )
            self._expressions_by_prec[prec] = expr
            self._expressions_by_desc[desc] = expr
            preceding_expr = expr

    def _guess_name_for_standin_token(self, standintoken: _standin_RGToken):
        if re.fullmatch(r"\w+(\s+\w+)*", standintoken.tok):
            standintoken.name = standintoken.tok
            standintoken.name_criteria = "tok"
        elif standintoken.opname:
            standintoken.name = standintoken.opname
            standintoken.name_criteria = "opname"
        elif len(standintoken.tok) == 1:
            standintoken.name = unicodedata.name(standintoken.tok)
            standintoken.name_criteria = "unicode"
        elif standintoken.tok == RG_TOK_NOT_EQUAL:
            standintoken.name = "not equal"
            standintoken.name_criteria = "hardcoded"
        else:
            raise ValueError(
                "unable to guess name for standin token",
                dict(standintoken=standintoken),
            )
        standintoken.name = CONSTANT_CASE(standintoken.name)

    def get_tokens(self) -> list[RGToken]:
        return list(self._token_by_name.values())

    def get_token_groups(self) -> list[RGEquivalentTokensGroup]:
        return list(self._token_group_by_name.values())

    def get_expressions(self) -> list[RGExpression]:
        return [e for p, e in sorted(self._expressions_by_prec.items())]

    def todo(self):
        print("!!", "TODO")
        print("!!", "TODO", inspect.stack()[1].function)
        print("!!", "TODO")


class RGWriter:
    def __init__(self, grammar: RG, lark_module_name=None, print=print):
        self.grammar = grammar
        self.lark_module_name = lark_module_name
        self.print = print

        self.names_for_import_example = []

    def write_header(self, header: str):
        self.print()
        self.print("//")
        self.print("//", header)
        self.print("//")
        self.print()

    def write_grammar(self):
        self.write_rules()
        self.write_terminals()
        if self.lark_module_name:
            self.print()
            for name in self.names_for_import_example:
                self.print(f"// %import {self.lark_module_name}.{name}")
            self.print()

    def write_rules(self):
        self.write_header("Rules")
        self.write_expression_rules()

    def write_terminals(self):
        self.write_header("Terminals")
        self.write_token_groups()
        self.write_tokens()

    def write_expression_rules(self):
        @functools.cache
        def _hook(name: str) -> str:
            return name.removesuffix("_expr") + "_hook"

        exprs = self.grammar.get_expressions()
        exprs.sort(key=lambda e: e.prec)
        lastexpr = exprs[-1]
        startexpr = RGExpression(
            prec=lastexpr.prec + 1,
            desc=LARK_START_RULE_NAME,
            left_assoc=False,
            preceding_expr=lastexpr,
            tokengroups=[],
        )
        exprs.append(startexpr)
        name_width = max(len(e.marked_name) for e in exprs)
        for expr in exprs:
            marked_hook = _hook(expr.name)
            altlines: list[list[str]] = []
            if expr.desc in {RG_DESC_PARENTHESES}:
                left = right = None
                for tg in expr.tokengroups:
                    if tg.namesake.tok in {RG_TOK_LEFT_PARENTHESIS}:
                        left = tg.name
                    if tg.namesake.tok in {RG_TOK_RIGHT_PARENTHESIS}:
                        right = tg.name
                if left is None:
                    raise ValueError("missing left parenthesis", dict(expr=expr))
                if right is None:
                    raise ValueError("missing right parenthesis", dict(expr=expr))
                altlines.append([left, marked_hook, right])
                altlines.append([LARK_VALUE_RULE_NAME, "", ""])
            elif expr.desc in {RG_DESC_UNARY_OPERATOR}:
                for tg in expr.tokengroups:
                    altlines.append([tg.name, marked_hook])
                altlines.append(["", marked_hook])
            elif expr.left_assoc:
                for tg in expr.tokengroups:
                    altlines.append([expr.name, tg.name, marked_hook])
                altlines.append(["", "", marked_hook])
            else:
                for tg in expr.tokengroups:
                    altlines.append([marked_hook, tg.name, expr.name])
                altlines.append([marked_hook, "", ""])
            for i in range(max(len(words) for words in altlines)):
                width = max(len(words[i]) for words in altlines if i < len(words))
                for words in altlines:
                    if i < len(words):
                        words[i] = words[i].ljust(width)
            prefix = expr.marked_name
            sep = ":"
            for words in altlines:
                self.print(prefix.ljust(name_width), sep, "  ".join(words))
                prefix = ""
                sep = "|"
            self.print()
            self.names_for_import_example.append(expr.name)

        for expr in exprs:
            marked_hook = _hook(expr.marked_name)
            hook = _hook(expr.name)
            preceding_name = (
                expr.preceding_expr.name
                if expr.preceding_expr is not None
                else LARK_START_RULE_NAME
            )
            self.print(marked_hook.ljust(name_width), ":", preceding_name)
            self.names_for_import_example.append(hook)

    def write_token_groups(self):
        groups = [g for g in self.grammar.get_token_groups() if len(g.tokens) != 1]
        groups.sort(key=lambda g: g.name)
        name_width = max(len(grp.marked_name) for grp in groups)
        for group in groups:
            prefix = group.name
            sep = ":"
            for token in sorted(group.tokens, reverse=True, key=lambda t: len(t.tok)):
                self.print(prefix.ljust(name_width), sep, token.name)
                prefix = ""
                sep = "|"
            self.print()
            self.names_for_import_example.append(group.name)

    def write_tokens(self):
        tokens = self.grammar.get_tokens()
        tokens.sort(key=lambda t: t.name)
        tokens_by_comment = collections.defaultdict(list)
        for token in tokens:
            tokens_by_comment[token.comment].append(token)
        pending_toks = {t.tok for t in tokens}
        name_width = max(len(tok.marked_name) for tok in tokens)
        for token in tokens:
            if token.tok in pending_toks:
                tokens_to_print: list[RGToken] = []
                if token.comment:
                    commentlines = [
                        cl.rstrip(".") + "." for cl in token.comment.split(". ")
                    ]
                    for cl in commentlines:
                        self.print("//", cl)
                    tokens_to_print.extend(tokens_by_comment[token.comment])
                else:
                    tokens_to_print.append(token)
                for token2 in tokens_to_print:
                    self.print(
                        token2.marked_name.ljust(name_width), ":", token2.escaped
                    )
                    pending_toks.remove(token2.tok)
                    self.names_for_import_example.append(token2.name)
                self.print()

    def todo(self):
        print("!!", "TODO")
        print("!!", "TODO", inspect.stack()[1].function)
        print("!!", "TODO")


@dataclasses.dataclass(frozen=True, order=True)
class RGToken:
    tok: str
    name: str
    prio: int
    comment: str

    # def __post_init__(self):
    #     object.__setattr__(self, "name", "_" + CONSTANT_CASE(self.name))

    @functools.cached_property
    def marked_name(self) -> str:
        if self.prio == 1:
            return self.name
        return self.name + "." + str(self.prio)

    @functools.cached_property
    def escaped(self) -> str:
        # if " " in self.tok:
        words = self.tok.split()
        escaped_words = list(map(re.escape, words))
        escaped = r"\s+".join(escaped_words)
        escaped = escaped.replace("/", r"\/")
        return "/" + escaped + "/"


@dataclasses.dataclass
class _standin_RGToken:
    tok: str
    prio: int = 1
    gvs: set[str] = dataclasses.field(default_factory=set)
    eff: str | None = None
    opname: str | None = None
    found_eqtok: bool = False
    name: str | None = None
    name_criteria: str | None = None

    def as_token(self) -> RGToken:
        if self.name is None:
            raise ValueError("name is None", dict(self=self))
        return RGToken(
            tok=self.tok, name=self.name, prio=self.prio, comment=self.eff or ""
        )


@dataclasses.dataclass(frozen=True, order=True)
class RGEquivalentTokensGroup:
    namesake: RGToken
    tokens: set[RGToken]

    @functools.cached_property
    def name(self) -> str:
        return (
            self.namesake.name
            if len(self.tokens) == 1
            else self.namesake.name + "_TOKENS"
        )

    @functools.cached_property
    def marked_name(self) -> str:
        return self.name


@dataclasses.dataclass(frozen=True, order=True)
class RGExpression:
    prec: float
    desc: str
    left_assoc: bool
    preceding_expr: RGExpression | None
    tokengroups: list[RGEquivalentTokensGroup]

    @functools.cached_property
    def name(self) -> str:
        if self.desc == LARK_START_RULE_NAME:
            return LARK_START_RULE_NAME
        n = snake_case(self.desc + " expr")
        if n is None:
            raise ValueError("calculated name is None", dict(self=self))
        return n

    @functools.cached_property
    def marked_name(self) -> str:
        return "?" + self.name


@dataclasses.dataclass
class _standin_RGExpression:
    gv: str
    prec: float
    tok: str
    desc: str
    left_assoc: bool = False


type FieldNameType = str
type FieldValueType = float | str
type RowType = dict[FieldNameType, FieldValueType]


def read_relevance_grammar_csv(csvfilename: str | pathlib.Path) -> list[RowType]:
    rows = []
    with open_file_for_csv_reader(csvfilename) as f:
        for row in csv.DictReader(f):
            row = {
                snake_case(k): trycast(v, FieldValueType)
                for k, v in row.items()
                if v not in {None, ""}
            }
            if RG_WORRY in row and row[RG_WORRY] in WORRIES_TO_IGNORE:
                continue
            if RG_TOKEN not in row and RG_ORIGINAL_GV in row:
                row[RG_TOKEN] = row.pop(RG_ORIGINAL_GV)
            rows.append(row)
    return rows


def noopprint(*args, **kwargs): ...


def TODO(*args, **kwargs):
    args = list(args)
    if not args or not isinstance(args[0], str):
        caller = inspect.stack()[1].function
        if caller != "<module>":
            args.insert(0, "Caller: " + caller + "()")
    if kwargs:
        args.append(dict(kwargs))
    raise NotImplementedError(*args)


def main():
    csvfilename = pathlib.Path(sys.argv[1])
    larkfilename = pathlib.Path(sys.argv[2])
    relevance_munge_grammar_csv_to_lark(csvfilename, larkfilename)


if __name__ == "__main__":
    try:
        main()
    except NotImplementedError as todo:
        dump(dict(TODO=list(todo.args)))
