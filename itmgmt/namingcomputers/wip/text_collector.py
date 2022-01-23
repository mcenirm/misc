class TextCollector:
    def __init__(self, owner=None) -> None:
        self.owner = owner
        self.buffer = None

    @property
    def expecting(self) -> bool:
        return self.buffer is not None

    def _assert_expecting(self) -> None:
        if not self.expecting:
            raise WasNotExpectingTextException(self)

    def _assert_not_expecting(self) -> None:
        if self.expecting:
            raise AlreadyExpectingTextException(self)

    def expect(self) -> None:
        self._assert_not_expecting()
        self.buffer = []

    def append(self, content: str) -> None:
        self._assert_expecting()
        self.buffer.append(content)

    def gather(self) -> str:
        self._assert_expecting()
        text = "".join(self.buffer)
        self.buffer = None
        return text


class TextCollectorException(Exception):
    def __init__(self, msg: str, text_collector: TextCollector) -> None:
        super().__init__(msg)
        self.text_collector = text_collector


class WasNotExpectingTextException(TextCollectorException):
    def __init__(self, text_collector: TextCollector) -> None:
        super().__init__("was not expecting text", text_collector)


class AlreadyExpectingTextException(TextCollectorException):
    def __init__(self, text_collector: TextCollector) -> None:
        super().__init__("already expecting text", text_collector)


if __name__ == "__main__":
    from io import StringIO
    from logging import warning
    from typing import Callable
    from xml.sax import make_parser
    from xml.sax.handler import ContentHandler

    class TagStackingContentHandler(ContentHandler):
        def __init__(self) -> None:
            super().__init__()
            self._stack = []

        @property
        def name(self) -> str:
            return self._stack[-1]

        def startElement(self, name, attrs) -> None:
            self._stack.append(name)

        def endElement(self, name) -> None:
            self._stack.pop()

    class SimpleTextCollectingContentHandler(TagStackingContentHandler):
        def __init__(
            self,
            expecting_text_tags: set[str],
            callback: Callable[[str], None] = print,
        ) -> None:
            super().__init__()
            self._expecting_text_tags = expecting_text_tags
            self._collector = TextCollector()
            self._callback = callback

        @property
        def expecting_text(self) -> bool:
            return self.name in self._expecting_text_tags

        def _warning_about_text_collector_exception(self, method) -> None:
            warning(
                "text collector exception in %r at %r",
                method.__name__,
                self._stack,
            )

        def startElement(self, name, attrs) -> None:
            super().startElement(name, attrs)
            if self.expecting_text:
                try:
                    self._collector.expect()
                except TextCollectorException:
                    self._warning_about_text_collector_exception(self.startElement)
                    raise

        def endElement(self, name) -> None:
            if self.expecting_text:
                try:
                    text = self._collector.gather()
                    self._callback(text)
                except TextCollectorException:
                    self._warning_about_text_collector_exception(self.startElement)
                    raise
            super().endElement(name)

        def characters(self, content) -> None:
            if self.expecting_text:
                self._collector.append(content)

    def make_xml(
        *,
        document_tag="document",
        message_tag="message",
        message="hello, world",
        number_of_messages=4,
    ):
        stanza = "<{0}>{1}</{0}>".format(message_tag, message)
        xml = "<{0}>{1}</{0}>".format(document_tag, stanza * number_of_messages)
        return xml

    message_tag = "message"
    xml_in = StringIO(make_xml(message_tag=message_tag))
    simple = SimpleTextCollectingContentHandler([message_tag])
    parser = make_parser()
    parser.setContentHandler(simple)
    parser.parse(xml_in)
