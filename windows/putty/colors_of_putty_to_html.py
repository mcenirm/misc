import contextlib
import dataclasses
import pathlib
import random
import re
import sys
import urllib.parse


############################################################


@dataclasses.dataclass
class Key:
    keypath: pathlib.PureWindowsPath
    values: dict[str, str] = dataclasses.field(default_factory=dict)
    defaultvalue: str | None = None

    def setdefaultvalue(self, value: str) -> None:
        if self.defaultvalue is not None:
            raise IndexError(
                "default value already set",
                dict(
                    keypath=self.keypath,
                    olddefaultvalue=self.defaultvalue,
                    newdefaultvalue=value,
                ),
            )
        else:
            self.defaultvalue = value

    def newvalue(self, name: str, value: str) -> None:
        if name in self.values:
            raise IndexError(
                "name exists",
                dict(
                    keypath=self.keypath,
                    name=name,
                    oldvalue=self.values[name],
                    newvalue=value,
                ),
            )
        else:
            self.values[name] = value


@dataclasses.dataclass
class RegistryExport:
    keys: dict[pathlib.PureWindowsPath, Key] = dataclasses.field(default_factory=dict)

    def newkey(self, keypath: str | pathlib.PureWindowsPath) -> Key:
        keypath = pathlib.PureWindowsPath(keypath)
        if keypath in self.keys:
            raise IndexError("key exists", dict(keypath=keypath))
        key = Key(keypath)
        self.keys[keypath] = key
        return key


def parse_reg_file(file_path: pathlib.Path) -> RegistryExport:
    registry: RegistryExport | None = None
    current_key: Key | None = None

    blank_pattern = re.compile(r"^\s*$")
    comment_pattern = re.compile(r"^;")
    # Windows Registry Editor Version 5.00
    header_pattern = re.compile(r"^Windows Registry Editor")
    # [Some\Path\To\A\Key]
    key_pattern = re.compile(r"^\[(.+)\]$")
    # "Name"="Value", "Number"=dword:0000000A, etc.
    named_value_pattern = re.compile(r'"([^"]+)"\s*=\s*(.*)$')
    # @="Value", @=dword:0000000A, etc.
    default_value_pattern = re.compile(r"@=\s*(.*)$")

    fp = pathlib.Path(file_path)
    maybe_bom = fp.read_bytes()[:2]
    if maybe_bom == b"\xff\xfe":
        encoding = "utf-16le"
    # elif maybe_bom == ???:
    else:
        encoding = "utf-8"

    raw_lines = fp.read_text(encoding=encoding).splitlines()

    # Try to handle contination lines
    lines = {lineno: line for lineno, line in enumerate(raw_lines, 1)}
    cont_lineno = None
    for lineno, line in enumerate(raw_lines, 1):
        if cont_lineno is None and line.endswith("\\"):
            cont_lineno = lineno
            lines[cont_lineno] = line[:-1]
        elif cont_lineno is not None and line.startswith("  "):
            if line.endswith("\\"):
                lines[cont_lineno] += line[2:-1]
            else:
                lines[cont_lineno] += line[2:]
                cont_lineno = None
            del lines[lineno]

    for lineno, line in lines.items():
        if blank_pattern.match(line):
            continue

        if comment_pattern.match(line):
            continue

        if header_pattern.match(line):
            continue

        m_key = key_pattern.match(line)
        if m_key:
            if registry is None:
                registry = RegistryExport()
            current_key = registry.newkey(m_key.group(1))
            continue

        m_def = default_value_pattern.match(line)
        if m_def and current_key:
            groups = list(m_def.groups())
            if len(groups) != 4 or groups[2] is not None or groups[3] is not None:
                print("++", lineno, groups)
                sys.exit(1)
            raw_value = groups.pop(0)
            current_key.setdefaultvalue(raw_value)
            continue

        m_val = named_value_pattern.match(line)
        if m_val and current_key:
            name, raw_value = m_val.groups()
            current_key.newvalue(name, raw_value.strip())
            continue

        raise ValueError("unexpected line", dict(lineno=lineno, line=line))

    return registry


############################################################


# <https://www.w3.org/WAI/WCAG21/Techniques/general/G18.html>
#
# 1. Measure the relative luminance of each letter (unless they are all uniform)
#    using the formula:
#
#    * L = 0.2126 * R + 0.7152 * G + 0.0722 * B where R, G and B are defined as:
#        * if R sRGB <= 0.04045
#          then R = R sRGB /12.92
#          else R = ((R sRGB +0.055)/1.055) ^ 2.4
#        * if G sRGB <= 0.04045
#          then G = G sRGB /12.92
#          else G = ((G sRGB +0.055)/1.055) ^ 2.4
#        * if B sRGB <= 0.04045
#          then B = B sRGB /12.92
#          else B = ((B sRGB +0.055)/1.055) ^ 2.4
#
#     Note
#     and R sRGB, G sRGB, and B sRGB are defined as:
#         R sRGB = R 8bit /255
#         G sRGB = G 8bit /255
#         B sRGB = B 8bit /255
#
#     Note
#     The "^" character is the exponentiation operator.
#
# Note
# For aliased letters, use the relative luminance value found
# two pixels in from the edge of the letter.
#
# 2. Measure the relative luminance of the background pixels
#    immediately next to the letter using same formula.
#
# 3. Calculate the contrast ratio using the following formula.
#
#    * (L1 + 0.05) / (L2 + 0.05), where
#        * L1 is the relative luminance of the lighter of
#          the foreground or background colors, and
#        * L2 is the relative luminance of the darker of
#          the foreground or background colors.
#
# 4. Check that the contrast ratio is equal to or greater than 4.5:1


@dataclasses.dataclass
class sRGB:
    r: float
    g: float
    b: float

    def __post_init__(self):
        bad_values = {n: v for n in "rgb" for v in [getattr(self, n)] if v < 0.0}
        if bad_values:
            raise ValueError(f"bad values", bad_values)
        if max(self.r, self.g, self.b) > 1.0:
            self.r = self.r / 255.0
            self.g = self.g / 255.0
            self.b = self.b / 255.0

    def relative_luminance(self) -> float:
        return sum(
            [
                0.2126 * linear(self.r),
                0.7152 * linear(self.g),
                0.0722 * linear(self.b),
            ]
        )

    def as_8bit(self) -> tuple[int, int, int]:
        return (
            clamp_8bit(self.r * 255),
            clamp_8bit(self.g * 255),
            clamp_8bit(self.b * 255),
        )

    def as_rrggbb(self) -> str:
        return "#{0:02x}{1:02x}{2:02x}".format(*self.as_8bit())


def clamp_8bit(n: int) -> int:
    return int(max(0, min(255, n)))


def linear(c: float) -> float:
    if c <= 0.04045:
        return c / 12.92
    else:
        return ((c + 0.055) / 1.055) ** 2.4


def contrast_ratio(fg: sRGB, bg: sRGB) -> float:
    l1 = fg.relative_luminance()
    l2 = bg.relative_luminance()
    if l2 > l1:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def check_contrast_ratio(fg: sRGB, bg: sRGB) -> float:
    return contrast_ratio(fg, bg) >= 4.5


def print_contrast_as_html_table() -> None:

    test_colors = [
        (c, c.as_rrggbb(), c.relative_luminance())
        for c in [
            sRGB(0, 0, 0),
            sRGB(0.5, 0.5, 0.5),
            sRGB(1, 1, 1),
        ]
        + [
            sRGB(
                random.uniform(x, x + 0.33),
                random.uniform(y, y + 0.33),
                random.uniform(z, z + 0.33),
            )
            for x in [0, 0.33, 0.66]
            for y in [0, 0.33, 0.66]
            for z in [0, 0.33, 0.66]
        ]
    ]

    # test_colors.sort(key=lambda t: t[0].relative_luminance())
    test_colors.sort(key=lambda t: t[2])

    print("<!DOCTYPE html>")
    print("<style> th { font-family: monospace} </style>")
    print("<table>")
    print("  <tr>")
    print("    <th>&nbsp;</th>")
    print("    <th>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</th>")
    for _, fg, _ in test_colors:
        print(f"    <th>{fg}</th>")
    print("  </tr>")
    print("  <tr>")
    print("    <th>&nbsp;</th>")
    print("    <th>&nbsp;</th>")
    for _, fg, _ in test_colors:
        print(f'    <th style="background-color: {fg}">&nbsp;</th>')
    print("  </tr>")
    print("  <tr>")
    print("    <th>&nbsp;</th>")
    print("    <th>&nbsp;</th>")
    for fgc, _, fgrl in test_colors:
        print(f"    <th>{round(fgrl,3)}</th>")
    print("  </tr>")
    for bgc, bg, bgrl in test_colors:
        print("  <tr>")
        print(f"    <th>{bg}</th>")
        print(f"    <th>{round(bgrl,3)}</th>")
        for fgc, fg, _ in test_colors:
            styles = {
                "background-color": bg,
                "color": fg,
            }
            if check_contrast_ratio(fgc, bgc):
                styles["font-weight"] = "bold"
            print(
                '    <td style="',
                "; ".join([f"{k}: {v}" for k, v in styles.items()]),
                '">',
                round(contrast_ratio(fgc, bgc), 3),
                "</td>",
            )
        print("  </tr>")
    print("</table>")


# with contextlib.redirect_stdout(
#     pathlib.Path("example.html").open("wt", encoding="utf-8")
# ):
#     print_contrast_as_html_table()


############################################################


SESSION_PATH = pathlib.PureWindowsPath(
    "HKEY_CURRENT_USER\\SOFTWARE\\SimonTatham\\PuTTY\\Sessions"
)

# References:
# <https://git.tartarus.org/?p=simon/putty.git;a=blob;f=putty.h;hb=HEAD>
# <https://git.tartarus.org/?p=simon/putty.git;a=blob;f=doc/man-pterm.but;hb=HEAD>

COLOUR_EXPLANATIONS = {
    "Colour0": "Default Foreground",
    "Colour1": "Default Bold Foreground",
    "Colour2": "Default Background",
    "Colour3": "Default Bold Background",
    "Colour4": "Cursor Text",
    "Colour5": "Cursor Colour",
    "Colour6": "ANSI Black",
    "Colour7": "ANSI Black Bold",
    "Colour8": "ANSI Red",
    "Colour9": "ANSI Red Bold",
    "Colour10": "ANSI Green",
    "Colour11": "ANSI Green Bold",
    "Colour12": "ANSI Yellow",
    "Colour13": "ANSI Yellow Bold",
    "Colour14": "ANSI Blue",
    "Colour15": "ANSI Blue Bold",
    "Colour16": "ANSI Magenta",
    "Colour17": "ANSI Magenta Bold",
    "Colour18": "ANSI Cyan",
    "Colour19": "ANSI Cyan Bold",
    "Colour20": "ANSI White",
    "Colour21": "ANSI White Bold",
}


for rp in pathlib.Path().glob("*.reg"):
    reg = parse_reg_file(rp)
    for keypath, key in reg.keys.items():
        if keypath.parent == SESSION_PATH:
            hp = rp.parent / (
                "colours "
                + rp.name.removesuffix(".reg")
                + "."
                + urllib.parse.unquote(keypath.name)
                + ".html"
            )
            print(hp)
            colours: dict[str, sRGB] = {}
            for name, value in key.values.items():
                if name.startswith("Colour"):
                    r, g, b = tuple(
                        map(int, value.removeprefix('"').removesuffix('"').split(","))
                    )
                    colours[name] = sRGB(r, g, b)
            if colours:
                blocks: list[str] = []
                black = sRGB(0, 0, 0)
                white = sRGB(1, 1, 1)
                for i, name in enumerate(COLOUR_EXPLANATIONS.keys()):
                    explanation = COLOUR_EXPLANATIONS[name]
                    if i % 2:
                        pass
                    else:
                        blocks.append("  <tr>")
                    if name in colours:
                        colour = colours[name]
                        bg_rrggbb = colour.as_rrggbb()
                        bg_r, bg_g, bg_b = colour.as_8bit()
                        fg_rrggbb = (
                            black
                            if contrast_ratio(black, colour)
                            > contrast_ratio(white, colour)
                            else white
                        ).as_rrggbb()
                        blocks.append(
                            f'    <td style="background-color: {bg_rrggbb}; color: {fg_rrggbb}">'
                            + f"<b>{bg_rrggbb}</b><br>"
                            + f"{bg_r},{bg_g},{bg_b}<br>"
                            + f"{name}<br>"
                            + f"<b>{explanation}</b></td>"
                        )
                    else:
                        blocks.append(
                            f"    <td>-------<br><br>{name}<br>{explanation}</td>"
                        )
                    if i % 2:
                        blocks.append("  </tr>")
                    else:
                        pass

                tdwidth = int(max(map(len, COLOUR_EXPLANATIONS.values())) * 0.6)
                html = (
                    [
                        "<!DOCTYPE html>",
                        "<style>",
                        f"  td {{ font-family: monospace; width: {tdwidth}em }}",
                        "</style>",
                        "<table>",
                    ]
                    + blocks
                    + [
                        "</table>",
                    ]
                )
                hp.write_text("".join([line + "\n" for line in html]))
