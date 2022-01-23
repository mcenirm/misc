import sys
from logging import warning
from typing import Any
from xml.sax import handler, make_parser

from icecream import ic
from rich import print as rprint

from mediawiki_export_util import EXPECTING_TEXT_TAGS, EXPORT_NS, SKIPS
from text_collector import TextCollector, TextCollectorException


class LimitExceededError(RuntimeError):
    def __init__(self, *args: object) -> None:
        super().__init__("limit exceeded", *args)


class Counter:
    def __init__(self, limit: int = 10) -> None:
        self.count = 0
        self.limit = limit

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        if self.count >= self.limit:
            raise LimitExceededError()
        self.count += 1


MSG0 = "-- %21s"
MSG_BEGIN = MSG0 + " <begin>"
MSG_END = MSG0 + " <end>"
MSG_INDEX = MSG0 + " [%d] %r"
MSG_KEY_VALUE = MSG0 + " %s = %r"


class NoisyContentHandler(handler.ContentHandler):
    def __init__(self, counter: Counter = None) -> None:
        super().__init__()
        self.counter = counter
        self.methods = []
        self.stack = []
        self.text = TextCollector()

    def _ww(self, fn: str, *args, **kwargs) -> None:
        if args or kwargs:
            warning(MSG_BEGIN, fn)
            for i, a in enumerate(args):
                warning(MSG_INDEX, fn, i, a)
            for k, v in kwargs.items():
                warning(MSG_KEY_VALUE, fn, k, v)
            warning(MSG_END, fn)
        else:
            warning(MSG0, fn)
        self.counter()

    def _w1kv(self, fn: str, k, v) -> None:
        warning(MSG_KEY_VALUE, fn, k, v)

    def _dot_stack(self) -> str:
        return ".".join(self.stack)

    def _current_tag(self) -> str:
        return self.stack[-1]

    def startDocumentXXXX(self):
        self._ww("startDocument")

    def endDocument(self):
        self._ww("endDocument")

    def startPrefixMappingXXXX(self, prefix, uri):
        self._ww("startPrefixMapping", prefix=prefix, uri=uri)

    def endPrefixMapping(self, prefix):
        self._ww("endPrefixMapping", prefix=prefix)

    def startElement(self, name, attrs):
        self._ww("startElement", name=name, attrs=attrs)

    def endElement(self, name):
        self._ww("endElement", name=name)

    def _start_or_end_element_ns(self, fn: str, name) -> None:
        try:
            is_start = fn == "startElementNS"
            uri, localname = name
            is_export = uri == EXPORT_NS
            is_skip = is_export and localname in SKIPS
            is_text = is_export and localname in EXPECTING_TEXT_TAGS
            k, v = ("localname", localname) if is_export else ("name", name)
            is_w1kv_needed = not (is_text or is_skip)
            if is_start:
                self.stack.append(localname)
                if is_text:
                    self.text.expect()
            else:
                self.stack.pop()
                if is_text:
                    text = self.text.gather()
                    rprint({self._dot_stack(): text})
            if is_w1kv_needed:
                self._w1kv(fn, k, v)
                self.counter()
        except TextCollectorException as tce:
            warning("text collector exception at in %r at %r", fn, self.stack)
            raise tce

    def startElementNS(self, name, qname, attrs):
        self._start_or_end_element_ns("startElementNS", name)

    def endElementNS(self, name, qname):
        self._start_or_end_element_ns("endElementNS", name)

    def characters(self, content):
        tag = self._current_tag()
        if tag in EXPECTING_TEXT_TAGS:
            self.text.append(content)
        elif tag not in SKIPS:
            self._w1kv("characters", "content", content)

    def ignorableWhitespace(self, whitespace):
        self._ww("ignorableWhitespace", whitespace=whitespace)

    def processingInstruction(self, target, data):
        self._ww("processingInstruction", target=target, data=data)

    def skippedEntity(self, name):
        self._ww("skippedEntity", name=name)


if __name__ == "__main__":
    counter = Counter(5)
    noisy = NoisyContentHandler(counter)
    parser = make_parser()
    parser.setFeature(handler.feature_namespaces, True)
    parser.setContentHandler(noisy)
    try:
        parser.parse(sys.argv[1])
    except LimitExceededError as lee:
        warning("%s", lee)
    except TextCollectorException as tce:
        warning("text collector exception", exc_info=tce)
    except Exception as e:
        warning("failure", exc_info=e)
    ic(noisy.stack)
