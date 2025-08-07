from __future__ import annotations

import dataclasses
import doctest
import enum
import re
import sys


def relevance_prelex(expression: str) -> list[PrelexedRelevanceToken]:
    """
    Convert a relevance expression to a list of tokens

    Tokens recognized:
     * Strings
     * Integers
     * Operators (punctuation)
     * Keywords
     * All other words

    >>> relevance_prelex(None)
    []
    >>> relevance_prelex("")
    []
    >>> relevance_prelex(" " * 20)
    []

    >>> [_.s for _ in relevance_prelex('"test"')]
    ['"test"']
    >>> [_.s for _ in relevance_prelex('"one %74%776f three"')]
    ['"one %74%776f three"']

    >>> relevance_prelex('"')
    Traceback (most recent call last):
    PrelexedRelevanceException: ('bad string', ...)
    >>> relevance_prelex('"50%"')
    Traceback (most recent call last):
    PrelexedRelevanceException: ('bad string', ...)

    >>> [(t.category.name, t.s) for t in relevance_prelex("123")]
    [('INTEGER', '123')]

    >>> [(t.category.name, t.normalized) for t in relevance_prelex("123a")]
    [('INTEGER', '123'), ('KEYWORD', 'A')]
    >>> [(t.category.name, t.normalized) for t in relevance_prelex("123XYZ")]
    [('INTEGER', '123'), ('WORD', 'xyz')]
    >>> [(t.category.name, t.normalized) for t in relevance_prelex("123Xyz456")]
    [('INTEGER', '123'), ('WORD', 'xyz456')]

    """

    if expression is None:
        return []
    pos = 0
    tokens = []
    while pos < len(expression):
        ch = expression[pos]
        tok = None
        if ch.isspace():
            pos += 1
            continue
        elif ch == '"':
            tok = expect_string(expression, pos)
        elif ch.isdigit():
            tok = expect_integer(expression, pos)
        elif ch.isalpha():
            tok = attempt_keyword(expression, pos) or expect_word(expression, pos)
        elif ch in OPERATOR_INDICATORS:
            tok = expect_operator(expression, pos)
        else:
            raise NotImplementedError(
                dict(
                    prob=expression[pos:],
                    expression=expression,
                    pos=pos,
                )
            )
        tokens.append(tok)
        pos = tok.endpos
    return tokens


def _set_to_regex_alternation_clause(st: set[str], fudge_ws=False) -> str:
    by_decreasing_length = sorted(st, key=len, reverse=True)
    if fudge_ws:
        alternations = [
            r"\s+".join([re.escape(w) for w in s.split()]) for s in by_decreasing_length
        ]
    else:
        alternations = [re.escape(s) for s in by_decreasing_length]
    return "|".join(alternations)


STRING_RE = re.compile(r'"([^"%]|%[0-9a-f][0-9a-f])*"', re.IGNORECASE)

INTEGER_RE = re.compile(r"[0-9]+")

KEYWORDS = {
    "a",
    "an",
    "and",
    "as",
    "contains",
    "does not contain",
    "does not end with",
    "does not equal",
    "does not start with",
    "else",
    "ends with",
    "equals",
    "exist",
    "exist no",
    "exists",
    "exists no",
    "false",
    "if",
    "is",
    "is contained by",
    "is equal to",
    "is greater than",
    "is greater than or equal to",
    "is less than",
    "is less than or equal to",
    "is not",
    "is not contained by",
    "is not equal to",
    "is not greater than",
    "is not greater than or equal to",
    "is not less than",
    "is not less than or equal to",
    "it",
    "item",
    "items",
    "mod",
    "nil",
    "not",
    "nothing",
    "nothings",
    "null",
    "number",
    "of",
    "or",
    "starts with",
    "the",
    "then",
    "there do not exist",
    "there does not exist",
    "there exist",
    "there exist no",
    "there exists",
    "there exists no",
    "true",
    "whose",
}
KEYWORDS_RE = re.compile(
    r"(" + _set_to_regex_alternation_clause(KEYWORDS, fudge_ws=True) + r")\b",
    re.IGNORECASE,
)

OPERATORS = {"=", "<", "&", ";", "(", ")", "*", ",", "+", ">", "/", "|", "-", "!="}
OPERATOR_TYPOS = {"\u2013": "-"}
OPERATOR_INDICATORS = set([op[0] for op in OPERATORS | OPERATOR_TYPOS.keys()])
OPERATORS_RE = re.compile(
    _set_to_regex_alternation_clause(OPERATORS | OPERATOR_TYPOS.keys())
)

WORD_RE = re.compile(r"[a-z][_a-z0-9]*", re.IGNORECASE)


class PrelexedRelevanceTokenCategory(enum.StrEnum):
    STRING = enum.auto()
    INTEGER = enum.auto()
    OPERATOR = enum.auto()
    KEYWORD = enum.auto()
    WORD = enum.auto()


@dataclasses.dataclass(frozen=True)
class PrelexedRelevanceToken:
    category: PrelexedRelevanceTokenCategory
    s: str
    pos: int
    endpos: int
    normalized: str = ""

    def __post_init__(self):
        if self.normalized == "":
            object.__setattr__(self, "normalized", self.s)


class PrelexedRelevanceException(BaseException): ...


def expect_string(expression: str, pos: int) -> PrelexedRelevanceToken:
    return expect_with_regex(
        STRING_RE,
        PrelexedRelevanceTokenCategory.STRING,
        expression,
        pos,
    )


def expect_integer(expression: str, pos: int) -> PrelexedRelevanceToken:
    return expect_with_regex(
        INTEGER_RE,
        PrelexedRelevanceTokenCategory.INTEGER,
        expression,
        pos,
    )


def attempt_keyword(expression: str, pos: int) -> PrelexedRelevanceToken | None:
    tok = attempt_with_regex(
        KEYWORDS_RE,
        PrelexedRelevanceTokenCategory.KEYWORD,
        expression,
        pos,
    )
    if tok:
        tok = PrelexedRelevanceToken(
            tok.category,
            tok.s,
            tok.pos,
            tok.endpos,
            "-".join(tok.s.split()).upper(),
        )
    return tok


def expect_word(expression: str, pos: int) -> PrelexedRelevanceToken:
    tok = expect_with_regex(
        WORD_RE,
        PrelexedRelevanceTokenCategory.WORD,
        expression,
        pos,
    )
    tok = PrelexedRelevanceToken(
        tok.category,
        tok.s,
        tok.pos,
        tok.endpos,
        tok.s.lower(),
    )
    return tok


def expect_operator(expression: str, pos: int) -> PrelexedRelevanceToken:
    tok = expect_with_regex(
        OPERATORS_RE,
        PrelexedRelevanceTokenCategory.OPERATOR,
        expression,
        pos,
    )
    if tok.s in OPERATOR_TYPOS:
        tok = PrelexedRelevanceToken(
            tok.category,
            OPERATOR_TYPOS[tok.s],
            tok.pos,
            tok.endpos,
        )
    return tok


def expect_with_regex(
    pat: re.Pattern,
    cat: PrelexedRelevanceTokenCategory,
    expression: str,
    pos: int,
) -> PrelexedRelevanceToken:
    tok = attempt_with_regex(pat, cat, expression, pos)
    if tok:
        return tok
    else:
        raise PrelexedRelevanceException(
            "bad " + str(cat).lower(), dict(expression=expression, pos=pos)
        )


def attempt_with_regex(
    pat: re.Pattern,
    cat: PrelexedRelevanceTokenCategory,
    expression: str,
    pos: int,
) -> PrelexedRelevanceToken | None:
    mat = pat.match(expression, pos=pos)
    if mat:
        return PrelexedRelevanceToken(cat, mat.group(0), pos, mat.end(0))
    else:
        return None


if __name__ == "__main__":
    if "--doctest" in sys.argv[1:]:
        doctest.testmod(optionflags=doctest.IGNORE_EXCEPTION_DETAIL | doctest.ELLIPSIS)
    else:
        for i, line in enumerate(
            open(sys.argv[1], "r", encoding="utf-8").readlines(), 1
        ):
            print(i, repr(line))
            for t in relevance_prelex(line):
                print("", t.category.name[0], t.s)
            print()
