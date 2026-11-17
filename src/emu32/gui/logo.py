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


def draw_logo(painter: QPainter, size: float) -> None:
    """Draw the logo into the square (0, 0, size, size)."""
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(size / GRID, size / GRID)

    # Small sizes (title bar, taskbar) use the whole square and a bolder, wider mark, so
    # the brackets and the triangle stay separate shapes at 16 px.
    small = size < 28
    tile = QPainterPath()
    tile.addRoundedRect(QRectF(0, 0, 64, 64) if small else QRectF(2, 2, 60, 60), 14, 14)
    shade = QLinearGradient(QPointF(2, 2), QPointF(62, 62))
    shade.setColorAt(0, QColor(dark.PALETTE["accent"]))
    shade.setColorAt(1, QColor(light.PALETTE["accent"]))
    painter.fillPath(tile, shade)

    ink = QColor(light.PALETTE["bg.base"])
    top, bottom = (14, 50) if small else (17, 47)
    sides = ((14, 21), (50, 43)) if small else ((17, 24), (47, 40))
    painter.setPen(QPen(ink, 6 if small else 5.5, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin))
    painter.setBrush(Qt.NoBrush)
    for edge, serif in sides:
        bracket = QPainterPath()
        bracket.moveTo(serif, top)
        bracket.lineTo(edge, top)
        bracket.lineTo(edge, bottom)
        bracket.lineTo(serif, bottom)
        painter.drawPath(bracket)

    painter.setPen(Qt.NoPen)
    painter.setBrush(ink)
    left, tip, half = (26, 42, 11) if small else (27.5, 40.5, 9)
    painter.drawPolygon(
        QPolygonF([QPointF(left, 32 - half), QPointF(left, 32 + half), QPointF(tip, 32)])
    )
    painter.restore()


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
