import codecs
import encodings
import encodings.utf_7
import encodings.utf_8
import encodings.utf_8_sig
import encodings.utf_16_be
import encodings.utf_16_le
import encodings.utf_32_be
import encodings.utf_32_le
import pathlib
import sys


def guess_encoding_of_existing_file(filename: str | pathlib.Path) -> str | None:
    filename = pathlib.Path(filename)
    tests = [
        (codecs.BOM_UTF8, encodings.utf_8_sig),
        (codecs.BOM_UTF32_LE, encodings.utf_32_le),
        (codecs.BOM_UTF16_LE, encodings.utf_16_le),
        (codecs.BOM_UTF32_BE, encodings.utf_32_be),
        (codecs.BOM_UTF16_BE, encodings.utf_16_be),
    ]
    bom = filename.read_bytes()[: max([len(p) for p, em in tests])]
    for prefix, enc_mod in tests:
        if bom.startswith(prefix):
            break
    else:
        enc_mod = None
    if enc_mod is None:
        if bom.startswith(b"\x2b\x2f\x76"):
            if len(bom) > 3:
                follower = int.from_bytes(bom[3], "big")
                if 0x38 <= follower <= 0x3F:
                    enc_mod = encodings.utf_7
        elif b"\x00" not in bom:
            enc_mod = encodings.utf_8
    if enc_mod is None:
        return None
    return enc_mod.getregentry().name


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:", pathlib.Path(__file__).stem, "file [...]", file=sys.stderr)
        sys.exit(1)
    else:
        for arg in sys.argv[1:]:
            enc = guess_encoding_of_existing_file(arg)
            print(f"{enc:10} {arg}")
