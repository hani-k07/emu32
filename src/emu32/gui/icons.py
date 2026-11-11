"""Toolbar icons: original line drawings, made at run time from theme tokens.

Each icon is drawn on a 24-unit grid with a 2-unit round stroke in one token color, so the
icons follow the theme and need no image files or icon font.
"""

from __future__ import annotations

from functools import cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPainterPath, QPen, QPixmap

from emu32.gui import theme

SCALE = 4  # pixels per grid unit; Qt scales the 96 px drawing down smoothly


def _new(p: QPainterPath) -> None:
    p.moveTo(14, 3)
    p.lineTo(6, 3)
    p.quadTo(4, 3, 4, 5)
    p.lineTo(4, 19)
    p.quadTo(4, 21, 6, 21)
    p.lineTo(18, 21)
    p.quadTo(20, 21, 20, 19)
    p.lineTo(20, 9)
    p.closeSubpath()
    p.moveTo(14, 3)
    p.lineTo(14, 9)
    p.lineTo(20, 9)
    p.moveTo(12, 12)
    p.lineTo(12, 18)
    p.moveTo(9, 15)
    p.lineTo(15, 15)


def _open(p: QPainterPath) -> None:
    p.moveTo(3, 18)
    p.lineTo(3, 6)
    p.quadTo(3, 4, 5, 4)
    p.lineTo(9, 4)
    p.lineTo(11, 7)
    p.lineTo(17, 7)
    p.quadTo(19, 7, 19, 9)
    p.lineTo(19, 10)
    p.moveTo(3, 18)
    p.lineTo(6, 11)
    p.quadTo(6.5, 10, 8, 10)
    p.lineTo(21, 10)
    p.lineTo(18, 18.5)
    p.quadTo(17.6, 19.5, 16, 19.5)
    p.lineTo(4.5, 19.5)
    p.quadTo(3, 19.5, 3, 18)


def _examples(p: QPainterPath) -> None:
    # An open book.
    p.moveTo(12, 7)
    p.quadTo(8, 4, 3, 5)
    p.lineTo(3, 18)
    p.quadTo(8, 17, 12, 20)
    p.quadTo(16, 17, 21, 18)
    p.lineTo(21, 5)
    p.quadTo(16, 4, 12, 7)
    p.lineTo(12, 20)


def _save(p: QPainterPath) -> None:
    p.moveTo(5, 3)
    p.lineTo(16, 3)
    p.lineTo(21, 8)
    p.lineTo(21, 19)
    p.quadTo(21, 21, 19, 21)
    p.lineTo(5, 21)
    p.quadTo(3, 21, 3, 19)
    p.lineTo(3, 5)
    p.quadTo(3, 3, 5, 3)
    p.moveTo(7, 3)
    p.lineTo(7, 8)
    p.lineTo(15, 8)
    p.lineTo(15, 3)
    p.addRoundedRect(QRectF(7, 13, 10, 8), 1, 1)


def _compile(p: QPainterPath) -> None:
    # A processor chip: source becomes machine code.
    p.addRoundedRect(QRectF(6, 6, 12, 12), 2, 2)
    p.addRect(QRectF(10, 10, 4, 4))
    for c in (9.5, 14.5):
        for a, b in ((2, 6), (18, 22)):
            p.moveTo(c, a)
            p.lineTo(c, b)
            p.moveTo(a, c)
            p.lineTo(b, c)


def _emulate(p: QPainterPath) -> None:
    p.moveTo(7, 4.5)
    p.lineTo(19, 12)
    p.lineTo(7, 19.5)
    p.closeSubpath()


def _calculator(p: QPainterPath) -> None:
    p.addRoundedRect(QRectF(5, 2.5, 14, 19), 2, 2)
    p.addRect(QRectF(8, 5.5, 8, 4))
    for y in (13, 17):
        for x in (8.5, 12, 15.5):
            p.addEllipse(QPointF(x, y), 0.4, 0.4)


def _converter(p: QPainterPath) -> None:
    p.moveTo(4, 8)
    p.lineTo(20, 8)
    p.moveTo(16, 4)
    p.lineTo(20, 8)
    p.lineTo(16, 12)
    p.moveTo(20, 16)
    p.lineTo(4, 16)
    p.moveTo(8, 12)
    p.lineTo(4, 16)
    p.lineTo(8, 20)


def _options(p: QPainterPath) -> None:
    # Three sliders.
    for y, knob in ((6, 15), (12, 8), (18, 13)):
        p.moveTo(4, y)
        p.lineTo(knob - 2, y)
        p.moveTo(knob + 2, y)
        p.lineTo(20, y)
        p.addEllipse(QPointF(knob, y), 2, 2)


def _help(p: QPainterPath) -> None:
    p.addEllipse(QPointF(12, 12), 9, 9)
    p.moveTo(9.3, 9.5)
    p.cubicTo(9.5, 6.5, 14.8, 6.5, 14.8, 9.6)
    p.cubicTo(14.8, 11.6, 12, 11.8, 12, 13.8)
    p.addEllipse(QPointF(12, 17), 0.3, 0.3)


def _about(p: QPainterPath) -> None:
    p.addEllipse(QPointF(12, 12), 9, 9)
    p.moveTo(12, 11)
    p.lineTo(12, 16.5)
    p.addEllipse(QPointF(12, 7.8), 0.3, 0.3)


def _close(p: QPainterPath) -> None:
    p.moveTo(7, 7)
    p.lineTo(17, 17)
    p.moveTo(17, 7)
    p.lineTo(7, 17)


# name -> (drawing, color token)
_ICONS = {
    "new": (_new, "text.primary"),
    "open": (_open, "warn"),
    "examples": (_examples, "syn.register"),
    "save": (_save, "accent"),
    "compile": (_compile, "syn.number"),
    "emulate": (_emulate, "ok"),
    "calculator": (_calculator, "syn.string"),
    "converter": (_converter, "syn.string"),
    "options": (_options, "text.primary"),
    "help": (_help, "accent"),
    "about": (_about, "accent"),
    "close": (_close, "text.muted"),
}


def icon(name: str) -> QIcon:
    return _icon(name, theme.current_name())


@cache
def _icon(name: str, theme_name: str) -> QIcon:
    draw, token = _ICONS[name]
    path = QPainterPath()
    draw(path)
    pixmap = QPixmap(24 * SCALE, 24 * SCALE)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(SCALE, SCALE)
    painter.setPen(QPen(theme.color(token), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    painter.drawPath(path)
    if name == "emulate":  # the play button is filled, so the main action stands out
        painter.fillPath(path, theme.color(token))
    painter.end()
    return QIcon(pixmap)
