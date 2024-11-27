from __future__ import annotations

import dataclasses
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
class SVGElement(dict):
    def tag(self) -> str:
        return self.__class__.__name__.replace("SVG", "", 1).lower()

    def attrib(self) -> dict[str, str]:
        d = {
            fld.name: str(getattr(self, fld.name))
            for fld in dataclasses.fields(self)
            if not fld.name.startswith("_")
        }
        d |= dict(self)
        return d

    def et(self) -> ET.Element:
        return ET.Element(_qn(self.tag()), self.attrib())


@dataclasses.dataclass
class SVGCanvas(SVGElement):
    viewBox: Box = dataclasses.field(default_factory=Box)
    width: CanvasDistance = 100
    height: CanvasDistance = 100
    _elements: list[SVGElement] = dataclasses.field(default_factory=list)

    def tag(self) -> str:
        return "svg"

    def attrib(self) -> dict[str, str]:
        d = super().attrib()
        d["viewBox"] = self.viewBox.as_attr()
        return d

    def append(self, element: SVGElement) -> None:
        self._elements.append(element)

    def write(self, file, **etree_write_kwargs) -> None:
        svg = self.et()
        for elem in self._elements:
            svg.append(elem.et())
        tree = ET.ElementTree(svg)
        ET.indent(tree)
        kwargs = dict(etree_write_kwargs)
        tree.write(file, **kwargs)


@dataclasses.dataclass
class SVGCircle(SVGElement):
    cx: BoxCoordinate
    cy: BoxCoordinate
    r: BoxDistance


@dataclasses.dataclass
class SVGLine(SVGElement):
    x1: BoxCoordinate
    y1: BoxCoordinate
    x2: BoxCoordinate
    y2: BoxCoordinate
