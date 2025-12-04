from __future__ import annotations

import csv
import pathlib
import re
import sys


CATEGORY = "category"
SUBCATEGORY = "subcategory"
RELATIVE_PRICE = "relative price"
MAKER = "maker"
BRAND = "brand"
MODEL = "model"
FIELDNAMES = [
    CATEGORY,
    SUBCATEGORY,
    RELATIVE_PRICE,
    MAKER,
    BRAND,
    MODEL,
]


def main():
    rowdicts: list[dict[str, object]] = []
    for lineno, line in enumerate(
        pathlib.Path(sys.argv[1]).read_text(encoding="utf8").splitlines(), 1
    ):
        if line == "":
            continue
        mtch = re.compile(
            (
                r"Selected"
                r"|"
                r"Dell Price\s*(?P<sign>[-+]?)\s*(?P<currency>\$)\s*(?P<price>[0-9,]+\.\d\d)"
            ),
            re.IGNORECASE,
        ).fullmatch(line)
        if mtch:
            sign = mtch.group("sign") or ""
            currency = mtch.group("currency") or "$"
            price = mtch.group("price") or "0.00"
            fmtdprice = format_price(price, sign, currency)
            rowdicts[-1].setdefault(RELATIVE_PRICE, fmtdprice)
        else:
            for pat in [
                re.compile(
                    r"(?P<category>Processor)(\s+Which\s+processor\s+is\s+right\s+for\s+you\?Collapse)?",
                    re.IGNORECASE,
                ),
                re.compile(
                    r"(?P<subcategory>Intel [45]th Gen|Others)",
                    re.IGNORECASE,
                ),
                re.compile(
                    (
                        r"("
                        r"("
                        r"(?P<maker>Intel)®?\s+(?P<brand>Xeon)®?\s+(?P<model>W[579]-\d\d\d\dX?)"
                        r")"
                        r")"
                        r"\s*"
                        r"\((?P<features>.*)\)"
                    ),
                    re.IGNORECASE,
                ),
            ]:
                mtch = pat.fullmatch(line)
                if mtch:
                    gd = mtch.groupdict()
                    features = gd.get("features", "")
                    if features:
                        featdict: dict[str, object] = {}
                        while features:
                            for featpat in [
                                re.compile(
                                    r"\s+",
                                ),
                                re.compile(
                                    r",+\s*",
                                ),
                                re.compile(
                                    r"(?P<cache>\d+)\s*(?P<cache_units>MB)\s+cache\b",
                                    re.IGNORECASE,
                                ),
                                re.compile(
                                    r"(?P<cores>\d+)\s*cores\b",
                                    re.IGNORECASE,
                                ),
                                re.compile(
                                    r"(?P<threads>\d+)\s*threads\b",
                                    re.IGNORECASE,
                                ),
                                re.compile(
                                    r"up\s+to\s+(?P<clockturbo>\d+(\.\d+)?)\s*(?P<clockturbo_units>GHz)\s+Turbo\b",
                                    re.IGNORECASE,
                                ),
                                re.compile(
                                    r"(?P<clock>\d+(\.\d+)?)\s*(?P<clock_units>GHz)\s+to\s+(?P<clockturbo>\d+(\.\d+)?)\s*(?P<clockturbo_units>GHz)\s+Turbo\b",
                                    re.IGNORECASE,
                                ),
                                re.compile(
                                    r"(?P<watts>\d+)\s*W\b",
                                    re.IGNORECASE,
                                ),
                            ]:
                                featmtch = featpat.match(features)
                                if featmtch:
                                    features = features[featmtch.end() :]
                                    featgd = featmtch.groupdict()
                                    if featgd:
                                        for k, v in featgd.items():
                                            if k in featdict:
                                                raise ValueError(
                                                    "duplicate feature",
                                                    lineno,
                                                    featdict,
                                                    featgd,
                                                )
                                            featdict[k] = v
                                        break
                            else:
                                raise ValueError(
                                    "unexpected features", lineno, features, featdict
                                )
                        _ = gd.pop("features")
                        gd.update(featdict)
                    rowdicts.append(dict(gd))
                    break
            else:
                raise ValueError("unexpected line", lineno, line)
    fieldnames = list(FIELDNAMES)
    for row in rowdicts:
        for k in row.keys():
            if k not in fieldnames:
                fieldnames.append(k)
    w = csv.DictWriter(sys.stdout, fieldnames)
    w.writeheader()
    cat = ""
    subcat = ""
    for row in rowdicts:
        if CATEGORY in row:
            cat = row[CATEGORY]
            continue
        else:
            row[CATEGORY] = cat
        if SUBCATEGORY in row:
            subcat = row[SUBCATEGORY]
            continue
        else:
            row[SUBCATEGORY] = subcat
        w.writerow(row)


def format_price(price: str, sign: str = "", currency: str = "$") -> str:
    return f"{currency}{sign}{float(price.replace(",","")):,.2f}"


if __name__ == "__main__":
    sys.exit(main())
