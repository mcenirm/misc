import bz2
from dataclasses import dataclass
from functools import cache
from typing import Any, Callable, Iterator, Optional, TextIO, Union

from lxml import etree  # type: ignore

from mediawiki_export_constants import (
    EXPORT_NS,
    FORMAT,
    MEDIAWIKI,
    MODEL,
    PAGE,
    TEXT,
    TITLE,
)

QFORMAT = etree.QName(EXPORT_NS, FORMAT)
QMEDIAWIKI = etree.QName(EXPORT_NS, MEDIAWIKI)
QMODEL = etree.QName(EXPORT_NS, MODEL)
QPAGE = etree.QName(EXPORT_NS, PAGE)
QTEXT = etree.QName(EXPORT_NS, TEXT)
QTITLE = etree.QName(EXPORT_NS, TITLE)


@dataclass
class Page:
    title: Optional[str]
    model: Optional[str]
    format: Optional[str]
    text: Optional[str]

    def to_lxml_etree_element(self) -> etree.Element:
        page = etree.Element(QPAGE)
        title = etree.Element(QTITLE)
        title.text = self.title
        page.append(title)
        model = etree.Element(QMODEL)
        model.text = self.model
        page.append(model)
        format = etree.Element(QFORMAT)
        format.text = self.format
        page.append(format)
        text = etree.Element(QTEXT)
        text.text = self.text
        page.append(text)
        return page


def opensesame(*args, **kwargs):
    try:
        f = bz2.open(*args, **kwargs)
        f.peek(0)
        return f
    except OSError as e:
        if e.args != ("Invalid data stream",):
            raise
    return open(*args, **kwargs)


@cache
def get_text_property(
    el: etree.Element,
    property_uri: str,
    property_local_name: str,
) -> Optional[str]:
    q = etree.QName(property_uri, property_local_name)
    for child in el:
        if child.tag == q:
            return get_element_as_text(child)
    return None


def get_element_as_text(el: etree.Element) -> Optional[str]:
    if len(el):
        return None
    return el.text or None


def pages(
    xmlfile,
    /,
    matcher: Callable[[Page], bool] = lambda page: True,
) -> Iterator[Page]:
    for page_el in page_elements(xmlfile):
        title = get_text_property(page_el, EXPORT_NS, TITLE)
        model = get_text_property(page_el, EXPORT_NS, MODEL)
        format_ = get_text_property(page_el, EXPORT_NS, FORMAT)
        text = get_text_property(page_el, EXPORT_NS, TEXT)
        page = Page(title, model, format_, text)
        if matcher(page):
            yield page


TextPropertiesDict = dict[str, Any]


def get_text_properties_as_dicts(el: etree.Element) -> Optional[TextPropertiesDict]:
    d = {}
    for child in el:
        q = etree.QName(child)
        if len(child):
            value = get_text_properties_as_dicts(child)
        else:
            value = child.text
        if value:
            d[q.localname] = value
    return d or None


def pages_as_dicts(xmlfile) -> Iterator[Optional[TextPropertiesDict]]:
    for page_el in page_elements(xmlfile):
        page_dict = get_text_properties_as_dicts(page_el)
        yield page_dict


def page_elements(xmlfile: TextIO) -> Iterator[etree.Element]:
    for _, page_el in etree.iterparse(xmlfile, tag=QPAGE):
        yield page_el
        page_el.clear(keep_tail=True)
