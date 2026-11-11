"""Light and dark themes, and the colors the editor and panels use for each."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class Colors:
    instruction: str
    register: str
    number: str
    string: str
    comment: str
    directive: str
    current_line: str
    gutter: str
    gutter_text: str
    breakpoint: str
    bookmark: str
    error: str
    changed: str


LIGHT = Colors(
    instruction="#1f4fb3",
    register="#7a2e8e",
    number="#a14a00",
    string="#2e7d32",
    comment="#6b7280",
    directive="#b3261e",
    current_line="#eef3fb",
    gutter="#f2f2f2",
    gutter_text="#8a8a8a",
    breakpoint="#d32f2f",
    bookmark="#1976d2",
    error="#f9a825",
    changed="#fff2a8",
)
DARK = Colors(
    instruction="#82aaff",
    register="#c792ea",
    number="#f7a76c",
    string="#a5d6a7",
    comment="#8b949e",
    directive="#ff8a80",
    current_line="#2a2f3a",
    gutter="#20232a",
    gutter_text="#7d8590",
    breakpoint="#ef5350",
    bookmark="#64b5f6",
    error="#ffd54f",
    changed="#5a4a00",
)

# Projector mode: black and white with strong accents.
CONTRAST = Colors(
    instruction="#5fd7ff",
    register="#ff87ff",
    number="#ffd75f",
    string="#87ff87",
    comment="#d0d0d0",
    directive="#ff8787",
    current_line="#3a3a00",
    gutter="#000000",
    gutter_text="#ffffff",
    breakpoint="#ff5555",
    bookmark="#5fd7ff",
    error="#ffd75f",
    changed="#5f00af",
)

_current = LIGHT
_current_name = "light"


def colors() -> Colors:
    return _current


_PALETTES = {
    "light": {
        QPalette.Window: "#f3f4f6",
        QPalette.WindowText: "#1f2328",
        QPalette.Base: "#ffffff",
        QPalette.AlternateBase: "#f6f8fa",
        QPalette.Text: "#1f2328",
        QPalette.Button: "#eceef1",
        QPalette.ButtonText: "#1f2328",
        QPalette.Highlight: "#3d6fd6",
        QPalette.HighlightedText: "#ffffff",
        QPalette.ToolTipBase: "#ffffe1",
        QPalette.ToolTipText: "#1f2328",
        QPalette.PlaceholderText: "#8a8f98",
        QPalette.Link: "#1f4fb3",
    },
    "contrast": {
        QPalette.Window: "#000000",
        QPalette.WindowText: "#ffffff",
        QPalette.Base: "#000000",
        QPalette.AlternateBase: "#1a1a1a",
        QPalette.Text: "#ffffff",
        QPalette.Button: "#1a1a1a",
        QPalette.ButtonText: "#ffffff",
        QPalette.Highlight: "#ffd400",
        QPalette.HighlightedText: "#000000",
        QPalette.ToolTipBase: "#000000",
        QPalette.ToolTipText: "#ffffff",
        QPalette.PlaceholderText: "#bdbdbd",
        QPalette.Link: "#5fd7ff",
    },
    "dark": {
        QPalette.Window: "#1b1e24",
        QPalette.WindowText: "#e6e6e6",
        QPalette.Base: "#16181d",
        QPalette.AlternateBase: "#20232a",
        QPalette.Text: "#e6e6e6",
        QPalette.Button: "#252932",
        QPalette.ButtonText: "#e6e6e6",
        QPalette.Highlight: "#3d6fd6",
        QPalette.HighlightedText: "#ffffff",
        QPalette.ToolTipBase: "#252932",
        QPalette.ToolTipText: "#e6e6e6",
        QPalette.PlaceholderText: "#7d8590",
        QPalette.Link: "#82aaff",
    },
}


def system_theme() -> str:
    """The theme matching the operating system's light or dark setting."""
    scheme = QApplication.instance().styleHints().colorScheme()
    return "dark" if scheme == Qt.ColorScheme.Dark else "light"


def apply(name: str) -> None:
    """Apply "light" or "dark" to the whole application. Both set every palette color, so
    the result does not depend on the system's own light or dark setting."""
    global _current, _current_name
    name = name if name in _PALETTES else "light"
    _current_name = name
    app = QApplication.instance()
    app.setStyle("Fusion")
    palette = QPalette()
    for role, color in _PALETTES[name].items():
        palette.setColor(role, QColor(color))
    # Disabled text (greyed-out actions) stays readable but clearly inactive.
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#8a8f98"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#8a8f98"))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#8a8f98"))
    app.setPalette(palette)
    _current = {"dark": DARK, "contrast": CONTRAST}.get(name, LIGHT)


def current_name() -> str:
    return _current_name
