"""Apply and switch themes at run time; give widgets their colors by token name."""

from __future__ import annotations

from functools import cache

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from emu32.gui.theme import contrast, dark, light, stylesheet
from emu32.gui.theme.tokens import COLOR_TOKENS, UI_POINT_SIZE

PALETTES = {"dark": dark.PALETTE, "light": light.PALETTE, "contrast": contrast.PALETTE}
CHOICES = (("dark", "Dark"), ("light", "Light"))  # contrast is projector mode, not a choice

_current = "dark"


def current_name() -> str:
    return _current


def token(name: str) -> str:
    """A color token's value, such as '#4F9CFF', in the active theme."""
    return PALETTES[_current][name]


def color(name: str) -> QColor:
    return _qcolor(_current, name)


@cache
def _qcolor(theme: str, name: str) -> QColor:
    return QColor(PALETTES[theme][name])


def system_theme() -> str:
    """The OS light or dark setting, for the first start. Dark when it cannot be read."""
    app = QApplication.instance()
    if app is not None and app.styleHints().colorScheme() == Qt.ColorScheme.Light:
        return "light"
    return "dark"


def apply(name: str) -> None:
    """Switch the whole application to a theme ("dark", "light" or "contrast")."""
    global _current
    _current = name if name in PALETTES else "dark"
    tokens = PALETTES[_current]
    app = QApplication.instance()
    app.setStyle("Fusion")
    palette = QPalette()
    roles = {
        QPalette.Window: "bg.panel",
        QPalette.WindowText: "text.primary",
        QPalette.Base: "bg.base",
        QPalette.AlternateBase: "bg.panel",
        QPalette.Text: "text.primary",
        QPalette.Button: "bg.raised",
        QPalette.ButtonText: "text.primary",
        QPalette.Highlight: "selection",
        QPalette.HighlightedText: "text.primary",
        QPalette.ToolTipBase: "bg.raised",
        QPalette.ToolTipText: "text.primary",
        QPalette.PlaceholderText: "text.muted",
        QPalette.Link: "accent",
        QPalette.BrightText: "error",
    }
    for role, name_ in roles.items():
        palette.setColor(role, QColor(tokens[name_]))
    for role in (QPalette.Text, QPalette.ButtonText, QPalette.WindowText):
        palette.setColor(QPalette.Disabled, role, QColor(tokens["text.muted"]))
    app.setPalette(palette)
    font = QFont(app.font())
    font.setPointSize(UI_POINT_SIZE)
    app.setFont(font)
    app.setStyleSheet(stylesheet.build(tokens))


assert all(set(p) == set(COLOR_TOKENS) for p in PALETTES.values()), "palettes differ"
