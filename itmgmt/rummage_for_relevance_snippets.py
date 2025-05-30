from __future__ import annotations

import dataclasses
import html
import pathlib
import sys
import xml.etree.ElementTree as ET

DOT = "•"


def rummage_markdown_for_relevance_snippets(md: pathlib.Path) -> list[str]:
    md = pathlib.Path(md)
    if md.is_file():
        snippets = []
        text = md.read_text(encoding="utf-8").splitlines()
        snippets.extend(qna_sessions_plain_text(text))
        # TODO developer.bigfix.com evaluator template blocks
        return snippets
    raise ValueError(dict(md=md))


def rummage_bes_xml_for_relevance(xfile: pathlib.Path) -> list[str]:
    xfile = pathlib.Path(xfile)
    print("!!", "xfile", xfile)
    tree = ET.parse(xfile)
    root = tree.getroot()
    snippets = []
    for rel in root.findall(".//Relevance"):
        snippets.append(rel.text)
    return snippets


def qna_sessions_plain_text(text: list[str]) -> list[str]:
    if not text:
        return []
    if isinstance(text, str):
        text = [text]
    results = []
    for i, line in enumerate(text):
        line = html.unescape(line.strip())
        if line.startswith("Q: "):
            for ignore in [" OR ()", " <Example>", '"Steve\'s iPhone"']:
                if line.find(ignore) >= 0:
                    # Ignore examples with placeholders
                    break
            else:
                next_i = i + 1
                if next_i < len(text) and text[next_i].startswith("E: "):
                    # Only add snippets that are not error examples
                    continue
                results.append(line.removeprefix("Q: ").strip())
    return results


@dataclasses.dataclass
class OneOfTheFiles:
    f: pathlib.Path
    arg: pathlib.Path


def all_the_files(*arg: pathlib.Path, predicate=None) -> list[OneOfTheFiles]:
    files = []
    if predicate is None:
        predicate = bool
    for a in arg:
        a = pathlib.Path(a)
        if a.is_dir():
            for f in a.rglob("*"):
                if predicate(f):
                    files.append(OneOfTheFiles(f, a))
        else:
            if predicate(a):
                files.append(OneOfTheFiles(a, a))
    return files


def main():
    all_snippets = set()
    rummage_fn_by_suffix = {
        ".md": rummage_markdown_for_relevance_snippets,
        ".bes": rummage_bes_xml_for_relevance,
    }
    suffixes = set(sorted(rummage_fn_by_suffix.keys()))
    counts_by_suffix = {s: 0 for s in suffixes}
    counts_with_snippets_by_suffix = {s: 0 for s in suffixes}
    fcount = 0
    for ootf in all_the_files(
        *[pathlib.Path(a) for a in sys.argv[1:]],
        predicate=lambda f: pathlib.Path(f).suffix in suffixes,
    ):
        f = ootf.f
        fcount += 1
        suffix = f.suffix
        if suffix not in suffixes:
            continue
        counts_by_suffix[suffix] += 1
        snippets = rummage_fn_by_suffix[suffix](f)
        if snippets:
            counts_with_snippets_by_suffix[suffix] += 1
            all_snippets.update(snippets)
    for suffix in suffixes:
        c = counts_by_suffix[suffix]
        cws = counts_with_snippets_by_suffix[suffix]
        print(f"{cws:6d} {c:6d} {suffix}")
    total_with_snippets = sum(counts_with_snippets_by_suffix.values())
    print("-" * 6, "-" * 6, "-" * max(map(len, suffixes)))
    print(f"{total_with_snippets:6d} {fcount:6d}")
    print(len(all_snippets))
    collected_snippets = pathlib.Path("relevance-snippets.txt")
    lines = [line + "\n" for line in sorted(all_snippets)]
    with collected_snippets.open("wt", encoding="utf-8") as out:
        out.writelines(lines)
    print("Wrote:", collected_snippets)


if __name__ == "__main__":
    main()
