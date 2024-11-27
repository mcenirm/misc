from __future__ import annotations

from unwisvg import SVGCanvas, SVGCircle, SVGLine

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

rose.append(circle)
for line in lines:
    rose.append(line)
rose.write("compassrose.svg")
