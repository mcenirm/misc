import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, cast
from xml.dom.minidom import Element, Node

import avro.errors  # type: ignore
import avro.schema  # type: ignore
import rich
from avro.datafile import DataFileReader, DataFileWriter  # type: ignore
from avro.io import DatumReader, DatumWriter  # type: ignore
from progress.counter import Counter  # type: ignore

from mediawiki_export_reading import opensesame, page_elements, pages, pages_as_dicts


@dataclass
class WriterAndPrefix:
    writer: DataFileReader
    prefix: str


class AvroWriterMapping:
    @staticmethod
    def _ns_and_prefix_for_page(page: dict, /) -> tuple[str, str]:
        ns = page.get("ns", "_missingns_")
        if ns in ("0", "_missingns_"):
            return ns, ""
        if ns == "":
            return "_empty_", ""
        title = page.get("title", "")
        prefix = title.split(":")[0]
        return ns, prefix

    @staticmethod
    def _outlabel_for_ns_and_prefix(ns: str, prefix: str, /) -> str:
        prefix = prefix.lower().replace(" ", "_")
        return "-".join([_ for _ in (ns, prefix) if _])

    def __init__(
        self,
        schema: avro.schema.Schema,
        outfprefix: Path,
        outfsuffix: str,
        /,
    ) -> None:
        self.schema = schema
        self.outfprefix = outfprefix
        self.outfsuffix = outfsuffix
        self.nsmap: dict[str, WriterAndPrefix] = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        for writer_and_prefix in self.nsmap.values():
            writer_and_prefix.writer.close()

    def _make_writer(self, outlabel: str) -> DataFileWriter:
        outfname = f"{self.outfprefix}-{outlabel}{self.outfsuffix}"
        writer = DataFileWriter(open(outfname, "wb"), DatumWriter(), self.schema)
        return writer

    def _writer_for_page(self, page: dict) -> DataFileWriter:
        ns, prefix = AvroWriterMapping._ns_and_prefix_for_page(page)
        if ns not in self.nsmap:
            outlabel = AvroWriterMapping._outlabel_for_ns_and_prefix(ns, prefix)
            logging.warning("new writer: %s", outlabel)
            self.nsmap[ns] = WriterAndPrefix(self._make_writer(outlabel), prefix)
        expected = self.nsmap[ns]
        if expected.prefix != prefix:
            title = page.get("title", None)
            raise ValueError(
                f"mismatched ns prefix at title {title!r}: expected {expected.prefix!r}, got {prefix!r}"
            )
        return expected.writer

    def append(self, page: dict) -> None:
        writer = self._writer_for_page(page)
        writer.append(page)


if __name__ == "__main__":
    infname = (sys.argv[1:] or ("enwiktionary/pages.avro",))[0]
    infpath = Path(infname)
    reader = DataFileReader(open(infname, "rb"), DatumReader())
    schema = avro.schema.parse(reader.schema)
    writers = AvroWriterMapping(schema, infpath.with_suffix(""), infpath.suffix)
    prgrss = Counter()
    with prgrss, reader, writers:
        for page in reader:
            prgrss.next()
            writers.append(page)
