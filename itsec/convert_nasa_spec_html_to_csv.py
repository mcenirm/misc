from collections import OrderedDict
from csv import DictWriter
from pathlib import Path
from sys import argv

from bs4 import BeautifulSoup


class ASCSItem(OrderedDict):
    MINFIELDS = [
        "Severity",
        "NASA ASCS ID",
        "Title",
    ]
    MINKEYS = set(MINFIELDS)
    FIELDS = MINFIELDS + [
        "Type",
        "Path",
        "Register",
        "Control Setting",
        "CIS Reference",
        "STIG Reference",
        "Other References",
    ]
    KEYS = set(FIELDS)
    IGNOREKEYS = {
        "Application",
        "Function",
        "Minimum Version",
        "Required Removal Date",
    }
    EXPECTEDKEYS = KEYS  # | IGNOREKEYS

    def __setitem__(self, k, v) -> None:
        if k not in ASCSItem.EXPECTEDKEYS:
            raise ValueError("unexpected key", k)
        return super().__setitem__(k, v)

    def assertkeys(self):
        ks = self.keys()
        assert ASCSItem.MINKEYS.issubset(ks), (
            "missing keys",
            ASCSItem.MINKEYS - ks,
            self,
        )
        assert ASCSItem.KEYS.issuperset(ks), ("missing keys", ks - ASCSItem.KEYS, self)

    def validate(self):
        ks = self.keys()
        return ASCSItem.MINKEYS.issubset(ks) and ASCSItem.KEYS.issuperset(ks)


def abridge(e):
    return repr(str(e)[:60])


def review(e):
    for i, c in enumerate(e.find_all(recursive=False)):
        print(i, abridge(c))


def get_section_id_and_title(sectiondiv, hname):
    h = sectiondiv.find(hname)
    id = h.get("id")
    title = " ".join(h.stripped_strings)
    return id, title


def find_e2(e1, name1, attrs1, name2, attr2name, attr2value):
    found = None
    for c in e1.find_all(
        name1,
        attrs1,
        recursive=False,
    ):
        e2 = c.find(name2)
        v2 = e2.get(attr2name)
        if v2 == attr2value:
            found = c
    return found


def find_section_by_id(div, sectclass, hname, id):
    return find_e2(
        div,
        "div",
        {"class": sectclass},
        hname,
        "id",
        id,
    )


def guess_severity_title(severitydiv):
    _, rawtitle = get_section_id_and_title(severitydiv, "h3")
    id, title = rawtitle.split(" ", maxsplit=1)
    return id, title


def guess_ascs_id_and_title(ascsdiv):
    _, rawtitle = get_section_id_and_title(ascsdiv, "h4")
    id, title = rawtitle.split(": ", maxsplit=1)
    return id, title


items = OrderedDict()


htmlfile = open(argv[1], "rb")

with htmlfile:
    soup = BeautifulSoup(htmlfile, features="html.parser", from_encoding="utf8")


html = soup.find("html")
body = html.find("body")
content = body.find("div", attrs={"id": "content"})
secconfdiv = find_section_by_id(
    content,
    "sect1",
    "h2",
    "_security_configurations",
)
secconfbody = secconfdiv.find("div", attrs={"class": "sectionbody"})
for i, severitydiv in enumerate(
    secconfbody.find_all(
        "div",
        attrs={"class", "sect2"},
        recursive=False,
    )
):
    severitytitle = guess_severity_title(severitydiv)
    for j, ascsdiv in enumerate(
        severitydiv.find_all(
            "div",
            attrs={"class", "sect3"},
            recursive=False,
        )
    ):
        ascsid, ascstitle = guess_ascs_id_and_title(ascsdiv)
        table = ascsdiv.find("table", recursive=False)
        assert bool(table), (i, j, ascsid, ascstitle, abridge(table))
        tbody = table.find("tbody")
        assert bool(tbody), (i, j, ascsid, ascstitle, abridge(table), abridge(tbody))
        item = ASCSItem()
        item["Title"] = ascstitle
        for k, tr in enumerate(tbody.find_all("tr", recursive=False)):
            th = tr.find("th")
            assert th is not None, (i, j, ascsid, ascstitle, k, abridge(tr))
            key = th.get_text(" ", strip=True)
            assert bool(key), (i, j, ascsid, ascstitle, k, abridge(th), abridge(key))
            td = tr.find("td")
            assert td is not None, (i, j, ascsid, ascstitle, k, abridge(tr))
            value = td.get_text(" ", strip=True)
            assert bool(value), (
                i,
                j,
                ascsid,
                ascstitle,
                k,
                abridge(td),
                abridge(value),
            )
            item[key] = value
        item.assertkeys()
        items[ascsid] = item

csvpath = Path(argv[1]).with_suffix(".csv")
print(csvpath)
csvfile = open(csvpath, "w", newline="")
with csvfile:
    w = DictWriter(csvfile, ASCSItem.FIELDS)
    w.writeheader()
    w.writerows(items.values())
