from __future__ import annotations

import dataclasses
import pathlib
import xml.etree.ElementTree as ET

_SVGNS = "http://www.w3.org/2000/svg"
ET.register_namespace("", _SVGNS)


def _qn(name: str) -> str:
    return f"{{{_SVGNS}}}{name}"


BoxCoordinate = BoxDistance = int
CanvasCoordinate = CanvasDistance = int


def _center(min_v: BoxCoordinate, size: BoxDistance) -> BoxCoordinate:
    return min_v + (size // 2)


@dataclasses.dataclass
class Box:
    x1: BoxCoordinate = 0
    y1: BoxCoordinate = 0
    width: BoxDistance = 100
    height: BoxDistance = 100

    @property
    def cx(self) -> BoxCoordinate:
        return _center(self.x1, self.width)

    @property
    def cy(self) -> BoxCoordinate:
        return _center(self.y1, self.height)

    @property
    def minor(self) -> BoxDistance:
        return min(self.width, self.height)

    @property
    def major(self) -> BoxDistance:
        return max(self.width, self.height)

    @property
    def x2(self) -> BoxCoordinate:
        return self.x1 + self.width

    @property
    def y2(self) -> BoxCoordinate:
        return self.y1 + self.height

    def scaled_centered_box(self, scale: float) -> Box:
        scaled_width = scale * self.width
        scaled_height = scale * self.height
        return Box(
            BoxCoordinate(self.cx - (scaled_width / 2)),
            BoxCoordinate(self.cy - (scaled_height / 2)),
            BoxDistance(scaled_width),
            BoxDistance(scaled_height),
        )

    def as_attr(self) -> str:
        return f"{self.x1} {self.y1} {self.width} {self.height}"


@dataclasses.dataclass
class _SVGElement(dict):
    def tag(self) -> str:
        return self.__class__.__name__.replace("SVG", "", 1).lower()

    def attrib(self) -> dict[str, str]:
        d = {fld.name: str(getattr(self, fld.name)) for fld in dataclasses.fields(self)}
        d |= dict(self)
        return d

    def et(self) -> ET.Element:
        return ET.Element(_qn(self.tag()), self.attrib())


@dataclasses.dataclass
class SVGCanvas(_SVGElement):
    viewBox: Box = dataclasses.field(default_factory=Box)
    width: CanvasDistance = 100
    height: CanvasDistance = 100

    def tag(self) -> str:
        return "svg"

    def attrib(self) -> dict[str, str]:
        d = super().attrib()
        d["viewBox"] = self.viewBox.as_attr()
        return d


@dataclasses.dataclass
class SVGCircle(_SVGElement):
    cx: BoxCoordinate
    cy: BoxCoordinate
    r: BoxDistance


@dataclasses.dataclass
class SVGLine(_SVGElement):
    x1: BoxCoordinate
    y1: BoxCoordinate
    x2: BoxCoordinate
    y2: BoxCoordinate


rose = SVGCanvas(width=400, height=400)
box90 = rose.viewBox.scaled_centered_box(0.9)
box60 = rose.viewBox.scaled_centered_box(0.6)
box40 = rose.viewBox.scaled_centered_box(0.4)
circle = SVGCircle(box90.cx, box90.cy, box90.minor // 2)
lines = [
    SVGLine(box90.cx, box90.y1, box60.cx, box60.y1),
    SVGLine(box90.cx, box90.y2, box60.cx, box60.y2),
    SVGLine(box90.x1, box90.cy, box60.x1, box60.cy),
    SVGLine(box90.x2, box90.cy, box60.x2, box60.cy),
    SVGLine(box90.cx, box90.y1, box40.x2, box40.y1),
    SVGLine(box90.cx, box90.y1, box40.x1, box40.y1),
    SVGLine(box90.cx, box90.y2, box40.x2, box40.y2),
    SVGLine(box90.cx, box90.y2, box40.x1, box40.y2),
    SVGLine(box90.x1, box90.cy, box40.x1, box40.y2),
    SVGLine(box90.x1, box90.cy, box40.x1, box40.y1),
    SVGLine(box90.x2, box90.cy, box40.x2, box40.y2),
    SVGLine(box90.x2, box90.cy, box40.x2, box40.y1),
]

for e in [circle, *lines]:
    e["stroke"] = "black"
    e["stroke-width"] = "2"
circle["fill"] = "none"

svg = rose.et()
svg.append(circle.et())
for line in lines:
    svg.append(line.et())
tree = ET.ElementTree(svg)
ET.indent(tree)
with open(pathlib.Path("compassrose.svg"), "wb") as out:
    tree.write(out)
