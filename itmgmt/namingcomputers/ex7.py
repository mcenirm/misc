import sys
from typing import cast
from xml.dom.minidom import Element, Node

import avro.errors  # type: ignore
import avro.schema  # type: ignore
import rich
from avro.datafile import DataFileReader, DataFileWriter  # type: ignore
from avro.io import DatumReader, DatumWriter  # type: ignore
from progress.counter import Counter  # type: ignore

from mediawiki_export_reading import opensesame, page_elements, pages, pages_as_dicts

if __name__ == "__main__":
    prgrss = Counter()
    infname = sys.argv[1]
    outfname = sys.argv[2]
    inf = opensesame(infname, "r")
    schema = avro.schema.parse(open("page.avsc", "rb").read())
    writer = DataFileWriter(open(outfname, "wb"), DatumWriter(), schema)
    with prgrss, inf, writer:
        for page in pages_as_dicts(inf):
            prgrss.next()
            try:
                writer.append(page)
            except avro.errors.AvroTypeException:
                rich.print(page)
                raise

    reader = DataFileReader(open(outfname, "rb"), DatumReader())
    with reader:
        for page in reader:
            rich.print(page)
            break
