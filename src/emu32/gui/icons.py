"""Toolbar icons, drawn at run time from theme tokens: a rounded tile with a symbol.

(P2 of the polish plan replaces these with one open-source icon set.)
"""

from __future__ import annotations

from functools import cache

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QIcon, QPainter, QPixmap

from emu32.gui import theme

# name -> (symbol, color token). Symbols are plain text characters, never emoji.
_TILES = {
    "new": ("+", "ok"),
    "open": ("⇧", "accent"),  # upwards white arrow
    "examples": ("≡", "syn.register"),  # identical to
    "save": ("↓", "ok"),  # downwards arrow
    "compile": ("⌘", "warn"),  # place of interest sign
    "emulate": ("►", "accent"),  # black right-pointing pointer
    "calculator": ("=", "border.control"),
    "converter": ("⇄", "border.control"),  # arrows left and right
    "options": ("⋮", "border.control"),  # vertical ellipsis
    "help": ("?", "accent"),
    "about": ("i", "accent"),
}


def icon(name: str) -> QIcon:
    return _icon(name, theme.current_name())


@cache
def _icon(name: str, theme_name: str) -> QIcon:
    symbol, token = _TILES[name]
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(theme.color(token))
    painter.drawRoundedRect(QRectF(4, 4, 56, 56), 12, 12)
    font = QFont()
    font.setPixelSize(38)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(theme.color("text.on-accent"))
    painter.drawText(QRectF(0, 0, 64, 64), Qt.AlignCenter, symbol)
    painter.end()
    return QIcon(pixmap)
