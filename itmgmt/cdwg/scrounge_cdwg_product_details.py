from __future__ import annotations

import collections.abc
import csv
import doctest
import itertools
import pathlib
import re
import sys
import urllib.parse

from bs4 import BeautifulSoup, Tag


def main():
    BRAND = "Brand"

    fieldcounts: dict[str, int] = {BRAND: 0}
    rows: list[dict[str, str]] = []

    for htmlfilename in sys.argv[1:]:
        htmlfile = pathlib.Path(htmlfilename)

        soup = BeautifulSoup(htmlfile.read_bytes(), "html.parser")
        for search_result in soup.select("div.search-result"):
            row: dict[str, str] = {}
            title, url = get_title_and_url(search_result)
            row["Title"] = title
            row["Product URL"] = url
            row["MFG#"] = get_mfg_code(search_result)
            row["CDW#"] = get_cdw_code(search_result)
            row["Availability"] = get_availability(search_result)
            row["Shipping check"] = get_shipping_check(search_result)
            row["Tech specs URL"] = get_technical_specifications_link(search_result)
            row["MSRP"] = get_msrp(search_result)
            price, description = get_price_and_description(search_result)
            row[disambiguate(description, row.keys())] = price

            basic_specs = get_table(
                search_result,
                "div.product-spec-listing",
                "div.product-spec-header",
                "div.product-spec-value",
            )
            ext_specs = get_table(
                search_result,
                "div.extended-specs-row",
                "div.extended-specs-key",
                "div.extended-specs-value",
            )
            for k, v in itertools.chain(ext_specs, basic_specs):
                if v == row.get(k):
                    continue
                else:
                    row[disambiguate(k, row.keys())] = v

            if BRAND not in row and title:
                row[BRAND], _ = title.split(maxsplit=1)

            for k in row.keys():
                if k not in fieldcounts:
                    fieldcounts[k] = 0
                fieldcounts[k] += 1
            rows.append(row)

    writer = csv.DictWriter(sys.stdout, fieldcounts.keys())
    writer.writeheader()
    writer.writerows(rows)


def get_cdwg_url(el: Tag, attr: str = "href") -> str:
    url = str(el.get(attr, ""))
    if url:
        url = urllib.parse.urljoin("https://www.cdwg.com/", url)
    return url


def get_title_and_url(search_result: Tag) -> tuple[str, str]:
    title, url = "", ""
    srpu = search_result.select_one("a.search-result-product-url")
    if srpu:
        title = simple(str(srpu.get("aria-label") or srpu.get_text()))
        url = get_cdwg_url(srpu)
    return title, url


def get_mfg_code(search_result: Tag) -> str:
    return get_simple_single_text(search_result, "span.mfg-code").removeprefix("MFG#: ")


def get_cdw_code(search_result: Tag) -> str:
    return get_simple_single_text(search_result, "span.cdw-code").removeprefix("CDW#: ")


def get_availability(search_result: Tag) -> str:
    return (
        get_simple_single_text(search_result, "div.is-available")
        .removeprefix("Availability:")
        .lstrip()
        .removeprefix("●")
        .lstrip()
    )


def get_shipping_check(search_result: Tag) -> str:
    return get_simple_single_text(search_result, "div.shipping-check")


def get_technical_specifications_link(search_result: Tag) -> str:
    url = ""
    esl = search_result.select_one("a.extended-specs-link")
    if esl:
        url = get_cdwg_url(esl)
    return url


def get_msrp(search_result: Tag) -> str:
    return get_simple_single_text(search_result, "div.price-msrp.single")


def get_price_and_description(search_result: Tag) -> tuple[str, str]:
    price, description = "", ""
    price_type_list = list(search_result.select("div.price-type"))
    if len(price_type_list) > 1:
        raise NotImplementedError("multiple price types", price_type_list)
    if price_type_list:
        price_type = price_type_list[0]
        price = get_simple_single_text(price_type, "div.price-type-price")
        description = get_simple_single_text(price_type, "div.price-type-description")
    if price and not description:
        description = "Price"
    return price, description


def get_simple_single_text(starting_el: Tag, selector: str) -> str:
    text = ""
    el = starting_el.select_one(selector)
    if el:
        text = simple_text(el)
    return text


def get_table(
    starting_el: Tag,
    row_selector: str,
    key_selector: str,
    value_selector: str,
) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for el in starting_el.select(row_selector):
        key_list = list(el.select(key_selector))
        if len(key_list) > 1:
            raise NotImplementedError("multiple keys", el)
        if key_list:
            key = simple_text(key_list[0]).removesuffix(":")
        else:
            key = ""
        value_list = list(el.select(value_selector))
        if len(value_list) > 1:
            raise NotImplementedError("multiple values", el)
        if value_list:
            value = simple_text(value_list[0])
        else:
            value = ""
        items.append((key, value))
    return items


def disambiguate(s: str, others: collections.abc.Set[str]) -> str:
    counter = 1
    disambiguated = s
    while disambiguated in others:
        counter += 1
        disambiguated = s + " " + str(counter)
    return disambiguated


def simple_text(el: Tag) -> str:
    return simple(el.get_text())


def simple(s: str) -> str:
    return concise(s, maxlen=-1)


def concise(s: str, maxlen: int = 60) -> str:
    cs = re.compile(r"\s+", re.MULTILINE).sub(" ", str(s).strip())
    if maxlen > 0:
        cs = cs[:maxlen]
    return cs


def print_concise_text_and_depth_and_moniker_recursively(starting_el: Tag):
    starting_depth = len(list(starting_el.parents))
    maxlen = 40
    for el in itertools.chain([starting_el], starting_el.descendants):
        if isinstance(el, Tag):
            depth = len(list(el.parents)) - starting_depth + 1
            text = concise(el.get_text(), maxlen=maxlen)
            mon = moniker(el)
            print(repr(text).ljust(maxlen + 2), "|", "." * depth, mon)


def moniker(el: Tag) -> str:
    cssclass = el.get("class")
    if cssclass:
        return el.name + "[" + " ".join(cssclass) + "]"
    else:
        return el.name


if __name__ == "__main__":
    if "--doctest" in sys.argv[1:]:
        _ = doctest.testmod(optionflags=doctest.FAIL_FAST | doctest.ELLIPSIS)
    else:
        main()
