from __future__ import annotations

import functools
import inspect
import pathlib
import typing

import lark


def relevance_lark_tester(
    grammarfilename: str | pathlib.Path,
    testfilename: str | pathlib.Path,
    print=print,
):
    grammarfilename = pathlib.Path(grammarfilename)
    testfilename = pathlib.Path(testfilename)

    # parser, lexer = "earley", "auto"
    # parser, lexer = "earley", "basic"
    # parser, lexer = "earley", "dynamic"
    # parser, lexer = "earley", "dynamic_complete"
    # parser, lexer = "lalr", "auto"
    # parser, lexer = "lalr", "basic"
    parser, lexer = "lalr", "contextual"
    # parser, lexer = "cyk", "auto"

    relevance = lark.Lark(
        grammar=grammarfilename.read_text(encoding="utf-8"), parser=parser, lexer=lexer
    )
    testexprs = testfilename.read_text(encoding="utf-8").splitlines()

    for expr in testexprs:
        if not expr or expr.startswith("#"):
            continue
        print(expr)
        try:
            tree = relevance.parse(expr)
            showtree(tree, print=print)
            showspans(tree, print=print)
            # print(re.sub(r"\b(Tree|Token)\(", "(", str(tree)))
            print()
        except lark.exceptions.UnexpectedInput as unexpected:
            # dump_object(vars(unexpected))
            print()
            print(str(unexpected).splitlines()[0])
            print(unexpected.get_context(expr))
            raise SystemExit()


def showtree(tree: lark.ParseTree, print=print):
    showbranch(tree, print=print)


DEFAULT_INDENT = " · "


def showbranch(
    branch: lark.Tree | lark.Token,
    indent=DEFAULT_INDENT,
    indent_suffix=DEFAULT_INDENT,
    print=print,
):
    if isinstance(branch, lark.Tree):
        # print(indent, type(branch), type(branch.data))
        print(indent, repr(branch.data))
        subindent = indent + indent_suffix
        for c in branch.children:
            showbranch(c, indent=subindent, indent_suffix=indent_suffix, print=print)
    elif isinstance(branch, lark.Token):
        # print(indent, type(branch))
        print(indent, repr(branch.type), ":", repr(branch.value))


def showspans(tree: lark.Tree, print=print) -> None:
    depthfirstshowspan(tree, print=print)


def depthfirstshowspan(branch: lark.Tree | lark.Token, print=print) -> tuple[int, int]:
    if isinstance(branch, lark.Tree):
        nonempties = {k: v for k, v in vars(branch).items() if v is not None}
        for k, v in sorted(nonempties.items()):
            # print("!!", k, type(v), repr(v))
            if k not in {
                "children",
                "data",
            }:
                print("!!", _lineno(), k, type(v), repr(v))
                raise SystemExit()
        spans = []
        for child in branch.children:
            spans.append(depthfirstshowspan(child, print=print))
        start = min([span[0] for span in spans])
        end = max([span[1] for span in spans])
        print(" " * (start), "^" * (end - start), sep="")
        return start, end
    elif isinstance(branch, lark.Token):
        nonempties = {
            k: v
            for k, v in {
                k: getattr(branch, k) for k in dir(branch) if not k.startswith("_")
            }.items()
            if v is not None and k not in dir(str)
        }
        if set(nonempties.keys()) != {
            "type",
            "value",
            "line",
            "end_line",
            "column",
            "end_column",
            "start_pos",
            "end_pos",
            "new_borrow_pos",
            "update",
        }:
            lines = []
            for k, v in sorted(nonempties.items()):
                lines.append([_lineno(), k, type(v), repr(v)])
            print_table(lines, "!!", print=print)
        if branch.start_pos is None:
            raise ValueError("bad start_pos", dict(token=branch))
        if branch.end_pos is None:
            raise ValueError("bad end_pos", dict(token=branch))
        print(" " * (branch.start_pos), branch.value, sep="")
        return branch.start_pos, branch.end_pos
    else:
        print("!!", _lineno(), type(branch))
        raise SystemExit()


def _lineno() -> int:
    cf = inspect.currentframe()
    if cf is None or cf.f_back is None:
        return -1
    return cf.f_back.f_lineno


def print_table(table: list[list[str]], *args: typing.Any, print=print):
    table = [[str(cell) if cell is not None else "" for cell in row] for row in table]
    widths = [0] * max(map(len, table))
    for row in table:
        for i, cell in enumerate(row):
            w = len(cell) + 1
            if w > widths[i]:
                widths[i] = w
    for row in table:
        print(*args, *[c.ljust(widths[i]) for i, c in enumerate(row)])


def main():
    relevance_lark_tester(
        grammarfilename=pathlib.Path("relevance.lark"),
        testfilename=pathlib.Path("relevance-snippets.txt"),
        print=functools.partial(
            print, file=pathlib.Path("tester.out").open("w", encoding="utf-8")
        ),
    )


if __name__ == "__main__":
    main()
