"""Built-in help: quick start, syntax and instruction reference (section 8.6)."""

from __future__ import annotations

from importlib import resources

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QListWidget, QTextBrowser, QWidget

PAGES = {
    "quickstart": "Quick start",
    "syntax": "Syntax reference",
    "instructions": "Instruction reference",
    "visual_studio": "Coming from Visual Studio",
}


def page_text(key: str) -> str:
    return (resources.files("emu32") / "help" / f"{key}.md").read_text(encoding="utf-8")


class HelpWindow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("emu32 help")
        self.pages = QListWidget()
        self.pages.addItems(list(PAGES.values()))
        self.pages.setMaximumWidth(200)
        self.text = QTextBrowser()
        self.text.setOpenExternalLinks(True)
        layout = QHBoxLayout(self)
        layout.addWidget(self.pages)
        layout.addWidget(self.text, 1)
        self.pages.currentRowChanged.connect(lambda row: self._show(list(PAGES)[row]))
        self.resize(900, 640)
        self.show_page("quickstart")

    def show_page(self, key: str) -> None:
        self.pages.setCurrentRow(list(PAGES).index(key))
        self._show(key)

    def _show(self, key: str) -> None:
        self.text.setMarkdown(page_text(key))
        self.setWindowTitle(f"{PAGES[key]} - emu32 help")


def show_help(owner: QWidget, page: str = "quickstart") -> HelpWindow:
    """Open the help window at a page, one per owner window."""
    window = owner.__dict__.get("_help_window")
    if window is None:
        window = HelpWindow(owner)
        window.setWindowFlag(Qt.Window)
        owner.__dict__["_help_window"] = window
    window.show_page(page)
    window.show()
    window.raise_()
    return window
