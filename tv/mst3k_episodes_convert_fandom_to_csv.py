from __future__ import annotations

import argparse
import collections
import collections.abc
import csv
import dataclasses
import inspect
import pathlib
import traceback
import typing

import bs4

import frustra.cmds


MST3K_EPISODES_FROM_FANDOM_URL = "https://mst3k.fandom.com/wiki/List_of_MST3K_Episodes"
MST3K_EPISODES_FROM_FANDOM_HEADER_ORD_ID = "#"
MST3K_EPISODES_FROM_FANDOM_HEADER_SE_ID = "Ep."
MST3K_EPISODES_FROM_FANDOM_HEADER_SUBJECT = "Movie"
MST3K_EPISODES_FROM_FANDOM_HEADER_AIRDATE = "Original Airdate"
MST3K_EPISODES_FROM_FANDOM_HEADER_RELEASES = "Releases"
MST3K_EPISODES_FROM_FANDOM_HEADER_SCREENSHOT = "Screenshot"
MST3K_EPISODES_FROM_FANDOM_HEADER_TITLE_ATTR_NAME = "title"
MST3K_EPISODES_FROM_FANDOM_HEADER_TITLE_SELECTOR = (
    f"a[{MST3K_EPISODES_FROM_FANDOM_HEADER_TITLE_ATTR_NAME}]"
)


@dataclasses.dataclass
class Episode:
    ord_id: str
    se_id: str
    subject: str
    airdate: str
    releases: str
    screenshot: str
    description: str
    title: str
    season: str


def convert_fandom_html_to_csv(
    list_of_mst3k_episodes_html: pathlib.Path,
    output_csv: pathlib.Path,
    list_of_mst3k_episodes_url: str = MST3K_EPISODES_FROM_FANDOM_URL,
):
    if list_of_mst3k_episodes_html.exists():
        markup = list_of_mst3k_episodes_html.read_text(encoding="utf-8")
        episodes = list(read_episodes_from_fandom_html(markup=markup))
        save_episodes_to_csv_file(episodes, output_csv)
    else:
        raise NotImplementedError(
            list_of_mst3k_episodes_html,
            list_of_mst3k_episodes_url,
            "need to download list of episodes to local file",
        )


@dataclasses.dataclass
class _SeasonTitleAndTable:
    title: str
    table: bs4.Tag


_P = typing.ParamSpec("_P")


class _GetSeasonTitleAndTableCallable(typing.Protocol[_P]):
    def __call__(
        self, soup: bs4.Tag, *args: _P.args, **kwds: _P.kwargs
    ) -> collections.abc.Iterable[_SeasonTitleAndTable]: ...


@dataclasses.dataclass
class _FandomSeason(_SeasonTitleAndTable):
    heading_tag: bs4.Tag


def _get_fandom_seasons(
    soup: bs4.Tag,
    season_heading_selector="h2:has(> span.mw-headline)",
    season_title_selector="span.mw-headline",
    season_table_tag_name="table",
) -> collections.abc.Generator[_FandomSeason, None, None]:
    for season_heading_tag in soup.select(season_heading_selector):
        season_title: str | None = None
        season_title_tag = season_heading_tag.select_one(season_title_selector)
        if season_title_tag:
            season_title = season_title_tag.get_text(strip=False).strip()
        else:
            raise NotImplementedError(season_heading_tag, "no season title")
        season_table_tag = season_heading_tag.find_next_sibling(season_table_tag_name)
        if season_table_tag:
            yield _FandomSeason(
                title=season_title,
                table=season_table_tag,
                heading_tag=season_heading_tag,
            )
        else:
            pass


@dataclasses.dataclass
class _FandomExpectedHeader(Episode):
    _title_header_text_list: list[str]
    _title_selector: str
    _title_attr_name: str


def read_episodes_from_fandom_html(
    markup: str,
    bs4_features: str | collections.abc.Sequence[str] | None = "html5lib",
    season_generator: _GetSeasonTitleAndTableCallable = _get_fandom_seasons,
    expected_header: _FandomExpectedHeader = _FandomExpectedHeader(
        ord_id=MST3K_EPISODES_FROM_FANDOM_HEADER_ORD_ID,
        se_id=MST3K_EPISODES_FROM_FANDOM_HEADER_SE_ID,
        subject=MST3K_EPISODES_FROM_FANDOM_HEADER_SUBJECT,
        airdate=MST3K_EPISODES_FROM_FANDOM_HEADER_AIRDATE,
        releases=MST3K_EPISODES_FROM_FANDOM_HEADER_RELEASES,
        screenshot=MST3K_EPISODES_FROM_FANDOM_HEADER_SCREENSHOT,
        description="",
        title="",
        season="",
        _title_header_text_list=[
            MST3K_EPISODES_FROM_FANDOM_HEADER_SE_ID,
            MST3K_EPISODES_FROM_FANDOM_HEADER_SUBJECT,
        ],
        _title_selector=MST3K_EPISODES_FROM_FANDOM_HEADER_TITLE_SELECTOR,
        _title_attr_name=MST3K_EPISODES_FROM_FANDOM_HEADER_TITLE_ATTR_NAME,
    ),
) -> collections.abc.Generator[Episode, None, None]:
    soup = bs4.BeautifulSoup(
        markup=markup,
        features=bs4_features,
    )
    expected_cell_text_to_field_name = {
        getattr(expected_header, f.name): f.name
        for f in dataclasses.fields(expected_header)
        if not f.name.startswith("_") and getattr(expected_header, f.name)
    }
    season_count = 0
    for season_i, season in enumerate(season_generator(soup)):
        cell_index_to_field_name: dict[int, str] = {}
        header_texts: list[str] = []
        title_index_list: list[int] = []
        ep_kwargs: dict[str, str] | None = None
        for row_i, row_tag in enumerate(season.table.find_all("tr")):
            if row_i:
                cell_tags = list(row_tag.find_all("td"))
                cell_texts = [t.get_text(strip=False).strip() for t in cell_tags]
                if len(cell_tags) == len(header_texts):
                    if ep_kwargs:
                        yield Episode(**ep_kwargs)
                    else:
                        pass
                    ep_kwargs = {
                        cell_index_to_field_name[cell_i]: cell_text
                        for cell_i, cell_text in enumerate(cell_texts)
                    }
                    ep_kwargs["season"] = season.title
                    title_tag: bs4.Tag | None = None
                    for title_i in title_index_list:
                        title_tag = cell_tags[title_i].select_one(
                            expected_header._title_selector
                        )
                        if title_tag:
                            ep_kwargs["title"] = str(
                                title_tag.get(expected_header._title_attr_name, "")
                            ).strip()
                            break
                    else:
                        raise NotImplementedError(
                            season_i,
                            season.title,
                            row_i,
                            *(cell_tags[title_i] for title_i in title_index_list),
                            "missing title",
                        )
                elif len(cell_tags) == 1:
                    if ep_kwargs:
                        ep_kwargs["description"] = (
                            cell_tags[0].get_text(strip=False).strip()
                        )
                    else:
                        raise NotImplementedError(
                            season_i,
                            season.title,
                            row_i,
                            "empty ep_kwargs when trying to add description",
                        )
                else:
                    raise TODO(
                        season_i,
                        season.title,
                        row_i,
                        cell_tags[0],
                        *cell_tags[0].children,
                    )
            else:
                for cell_i, cell_tag in enumerate(row_tag.find_all("th")):
                    cell_text = cell_tag.get_text(strip=False).strip()
                    if cell_text in expected_cell_text_to_field_name:
                        field_name = expected_cell_text_to_field_name[cell_text]
                        if cell_text in header_texts:
                            raise NotImplementedError(
                                season_i,
                                season.title,
                                cell_i,
                                cell_text,
                                field_name,
                                "---------",
                                *header_texts,
                                "---------",
                                "duplicate cell text in header",
                            )
                        else:
                            header_texts.append(cell_text)
                            cell_index_to_field_name[cell_i] = field_name
                    else:
                        raise NotImplementedError(
                            cell_i,
                            cell_tag,
                            cell_text,
                            "text not in expected fields",
                            *expected_cell_text_to_field_name.items(),
                        )
                if header_texts:
                    for t in expected_header._title_header_text_list:
                        title_index_list.append(header_texts.index(t))
                else:
                    raise NotImplementedError(
                        season_i,
                        season.title,
                        "no header cells",
                    )
                if title_index_list:
                    pass
                else:
                    raise NotImplementedError(
                        season_i,
                        season.title,
                        expected_header._title_header_text_list,
                        *enumerate(header_texts),
                        "no title index",
                    )
        if ep_kwargs:
            yield Episode(**ep_kwargs)
        else:
            pass
        season_count += 1
    if season_count:
        pass
    else:
        raise NotImplementedError("no seasons found")


def save_episodes_to_csv_file(episodes, output_csv):
    with open(output_csv, "w") as out:
        wrtr = csv.DictWriter(
            out, fieldnames=[f.name for f in dataclasses.fields(episodes[0])]
        )
        wrtr.writeheader()
        wrtr.writerows(dataclasses.asdict(e) for e in episodes)


def _get_bs4_path_with_class(elem: bs4.element.PageElement, sep="/") -> str:
    items = []
    for item in list(reversed(list(elem.parents))) + [elem]:
        if isinstance(item, bs4.Tag):
            s = item.name
            c = item.get("class")
            if c:
                s = s + "[" + " ".join(sorted(c)) + "]"
        elif isinstance(item, bs4.element.NavigableString):
            s = "text()"
        else:
            s = type(item).__name__
        items.append(s)
    return sep.join(items)


class TODO(BaseException): ...


def main():
    f = convert_fandom_html_to_csv
    ap = frustra.cmds.argument_parser_from_function(f)
    args = ap.parse_args().__dict__
    try:
        return f(**args)
    except (TODO, NotImplementedError) as e:
        print(type(e).__name__)
        for a in e.args:
            r = a
            if r is not None:
                r = repr(r)
                if "\n" in r:
                    r = repr(str(a))
                r = r[:80]
            print(" ●", r)
        print()
        print(traceback.format_exception(e)[-2])
        print()


if __name__ == "__main__":
    main()
