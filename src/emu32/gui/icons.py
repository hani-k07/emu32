"""Toolbar icons, drawn at run time: a rounded tile with a symbol. No image files."""

from __future__ import annotations

from functools import cache

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap

_TILES = {
    "new": ("+", "#2e7d32"),
    "open": ("↗", "#1565c0"),  # north-east arrow
    "examples": ("≡", "#6a1b9a"),  # three bars
    "save": ("↓", "#00695c"),  # down arrow
    "compile": ("⚙", "#ef6c00"),  # gear
    "emulate": ("▶", "#c62828"),  # play triangle
    "calculator": ("=", "#455a64"),
    "converter": ("⇄", "#455a64"),  # two arrows
    "options": ("☰", "#5d4037"),  # trigram
    "help": ("?", "#1565c0"),
    "about": ("i", "#1565c0"),
}


@cache
def icon(name: str) -> QIcon:
    symbol, color = _TILES[name]
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(color))
    painter.drawRoundedRect(QRectF(4, 4, 56, 56), 12, 12)
    font = QFont()
    font.setPixelSize(38)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor("white"))
    painter.drawText(QRectF(0, 0, 64, 64), Qt.AlignCenter, symbol)
    painter.end()
    return QIcon(pixmap)
