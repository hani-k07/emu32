"""The emu32 logo: an original mark, drawn at run time (no image files in the package).

A blue tile with a memory operand's square brackets around a step triangle: "what is in
memory, one step at a time". The colors are fixed palette values, not the active theme, so
the logo looks the same everywhere. See docs/brand.md.
"""

from __future__ import annotations

import struct
from functools import cache

from PySide6.QtCore import QBuffer, QIODevice, QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
)

from emu32.gui.theme import dark, light

GRID = 64  # the mark is drawn on a 64-unit square
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)  # what Windows asks an icon for


def _shapes(small: bool) -> dict:
    """The logo's geometry on the 64-unit grid. Small sizes (title bar, taskbar) use the
    whole square and a bolder, wider mark, so the brackets and the triangle stay separate
    shapes at 16 px."""
    top, bottom = (14, 50) if small else (17, 47)
    sides = ((14, 21), (50, 43)) if small else ((17, 24), (47, 40))
    left, tip, half = (26, 42, 11) if small else (27.5, 40.5, 9)
    return {
        "tile": (0, 0, 64, 64) if small else (2, 2, 60, 60),
        "brackets": [
            [(serif, top), (edge, top), (edge, bottom), (serif, bottom)] for edge, serif in sides
        ],
        "stroke": 6 if small else 5.5,
        "triangle": [(left, 32 - half), (left, 32 + half), (tip, 32)],
    }


GRADIENT = (dark.PALETTE["accent"], light.PALETTE["accent"])  # top left to bottom right
INK = light.PALETTE["bg.base"]
CORNER = 14


def draw_logo(painter: QPainter, size: float) -> None:
    """Draw the logo into the square (0, 0, size, size)."""
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(size / GRID, size / GRID)
    shapes = _shapes(size < 28)

    tile = QPainterPath()
    tile.addRoundedRect(QRectF(*shapes["tile"]), CORNER, CORNER)
    shade = QLinearGradient(QPointF(2, 2), QPointF(62, 62))
    shade.setColorAt(0, QColor(GRADIENT[0]))
    shade.setColorAt(1, QColor(GRADIENT[1]))
    painter.fillPath(tile, shade)

    ink = QColor(INK)
    painter.setPen(QPen(ink, shapes["stroke"], Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
    painter.setBrush(Qt.NoBrush)
    for points in shapes["brackets"]:
        bracket = QPainterPath()
        bracket.moveTo(*points[0])
        for point in points[1:]:
            bracket.lineTo(*point)
        painter.drawPath(bracket)

    painter.setPen(Qt.NoPen)
    painter.setBrush(ink)
    painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in shapes["triangle"]]))
    painter.restore()


def _svg_mark(x: float = 0, y: float = 0) -> str:
    shapes = _shapes(small=False)
    tx, ty, tw, th = shapes["tile"]

    def points(pairs):
        return " ".join(f"{px:g},{py:g}" for px, py in pairs)

    lines = [
        f'<g transform="translate({x:g} {y:g})">',
        f'<rect x="{tx}" y="{ty}" width="{tw}" height="{th}" rx="{CORNER}" fill="url(#shade)"/>',
        *(
            f'<polyline points="{points(b)}" fill="none" stroke="{INK}" '
            f'stroke-width="{shapes["stroke"]:g}" stroke-linecap="square" '
            'stroke-linejoin="miter"/>'
            for b in shapes["brackets"]
        ),
        f'<polygon points="{points(shapes["triangle"])}" fill="{INK}"/>',
        "</g>",
    ]
    return "\n".join(lines)


def _svg(width: int, height: int, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        '<defs><linearGradient id="shade" x1="2" y1="2" x2="62" y2="62" '
        'gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{GRADIENT[0]}"/>'
        f'<stop offset="1" stop-color="{GRADIENT[1]}"/></linearGradient></defs>\n'
        f"{body}\n</svg>\n"
    )


def logo_svg() -> str:
    """The logo as SVG, from the same geometry as draw_logo (large form)."""
    return _svg(GRID, GRID, _svg_mark())


def banner_svg(theme_name: str) -> str:
    """The logo and the name, for the README on a light or dark page."""
    palette = (dark if theme_name == "dark" else light).PALETTE
    text = (
        f'<text x="80" y="46" font-family="Segoe UI, Helvetica, Arial, sans-serif" '
        f'font-size="40" font-weight="700" fill="{palette["text.primary"]}">emu32</text>'
    )
    return _svg(200, 64, _svg_mark() + "\n" + text)


@cache
def logo_image(size: int) -> QImage:
    image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    draw_logo(painter, size)
    painter.end()
    return image


def app_icon() -> QIcon:
    from PySide6.QtGui import QPixmap

    icon = QIcon()
    for size in SIZES:
        icon.addPixmap(QPixmap.fromImage(logo_image(size)))
    return icon


def ico_bytes() -> bytes:
    """The logo as a Windows .ico file with every size in SIZES (PNG entries)."""
    images = []
    for size in SIZES:
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        logo_image(size).save(buffer, "PNG")
        images.append((size, bytes(buffer.data())))
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries = b""
    for size, data in images:
        side = 0 if size == 256 else size  # 0 means 256 in an .ico directory
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return header + entries + b"".join(data for _, data in images)


def wizard_images() -> dict[str, QImage]:
    """Inno Setup wizard images at 100, 150 and 200 percent: the tall side image of the
    first and last pages (164 x 314 at 100 percent) and the small top-right image
    (55 x 55). 24-bit BMP, which every Inno Setup 6 version reads. No text: the build
    draws these offscreen, where fonts may be missing, and the wizard names emu32 itself."""
    images = {}
    for scale, suffix in ((1.0, "100"), (1.5, "150"), (2.0, "200")):
        width, height = round(164 * scale), round(314 * scale)
        side = QImage(width, height, QImage.Format_RGB888)
        painter = QPainter(side)
        painter.setRenderHint(QPainter.Antialiasing)
        shade = QLinearGradient(QPointF(0, 0), QPointF(0, height))
        shade.setColorAt(0, QColor(dark.PALETTE["bg.raised"]))
        shade.setColorAt(1, QColor(dark.PALETTE["bg.base"]))
        painter.fillRect(side.rect(), shade)
        mark = round(88 * scale)
        painter.translate((width - mark) / 2, round(96 * scale))
        draw_logo(painter, mark)
        painter.end()
        images[f"side{suffix}.bmp"] = side

        size = round(55 * scale)
        small = QImage(size, size, QImage.Format_RGB888)
        small.fill(QColor(light.PALETTE["bg.base"]))  # the wizard's top bar is white
        painter = QPainter(small)
        draw_logo(painter, size)
        painter.end()
        images[f"small{suffix}.bmp"] = small
    return images
