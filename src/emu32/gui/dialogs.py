"""Welcome, new file, find and replace, options and about dialogs."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from emu32 import __version__
from emu32.gui.templates import TEMPLATES
from emu32.gui.theme import CHOICES

REPOSITORY = "https://github.com/hani-k07/emu32"
AUTHOR = "hani-k07"
LICENSE_TEXT = "Free software under the GNU General Public License, version 2 or later."


class WelcomeDialog(QDialog):
    """Start screen. `choice` is "new", "examples", "tutorial" or a recent file path."""

    def __init__(self, recent: list[str], show_at_start: bool, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to emu32")
        self.choice: str | None = None
        grid = QGridLayout()
        for index, (key, label) in enumerate(
            (
                ("new", "&New"),
                ("examples", "Code &examples"),
                ("tutorial", "&Quick start tutorial"),
                ("recent", "&Recent files"),
            )
        ):
            button = QPushButton(label)
            button.setMinimumSize(200, 64)
            button.setObjectName(key)
            button.clicked.connect(lambda _=False, k=key: self._pick(k))
            grid.addWidget(button, index // 2, index % 2)
        self.recent_list = QListWidget()
        self.recent_list.addItems(recent)
        self.recent_list.setVisible(False)
        self.recent_list.itemActivated.connect(lambda item: self._finish(item.text()))
        self.show_at_start = QCheckBox("Show this window at start")
        self.show_at_start.setChecked(show_at_start)
        about = QLabel(
            f'emu32 {__version__}. {LICENSE_TEXT}<br><a href="{REPOSITORY}">{REPOSITORY}</a>'
        )
        about.setOpenExternalLinks(True)
        about.setWordWrap(True)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(grid)
        layout.addWidget(self.recent_list)
        layout.addWidget(self.show_at_start)
        layout.addWidget(about)
        layout.addWidget(close)

    def _pick(self, key: str) -> None:
        if key == "recent":
            self.recent_list.setVisible(not self.recent_list.isVisible())
            if self.recent_list.count() == 0:
                self.recent_list.addItem("(no recent files)")
                self.recent_list.item(0).setFlags(Qt.NoItemFlags)
            return
        self._finish(key)

    def _finish(self, choice: str) -> None:
        self.choice = choice
        self.accept()


class NewFileDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New file")
        self.group = QButtonGroup(self)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Start from:"))
        for key, label in (
            ("console", "32-bit &console program (MASM style)"),
            ("library", "32-bit with &library routines"),
            ("empty", "&Empty workspace"),
        ):
            radio = QRadioButton(label)
            radio.setObjectName(key)
            self.group.addButton(radio)
            layout.addWidget(radio)
        self.group.buttons()[0].setChecked(True)
        self.intel = QCheckBox("Use &Intel/NASM syntax")
        layout.addWidget(self.intel)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def template_key(self) -> str:
        return self.group.checkedButton().objectName()

    def source(self) -> str:
        return TEMPLATES[(self.template_key(), self.intel.isChecked())]


class FindReplaceDialog(QDialog):
    """Non-modal find and replace over one QPlainTextEdit at a time."""

    message = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Find and replace")
        self.editor: QPlainTextEdit | None = None
        self.find_text = QLineEdit()
        self.replace_text = QLineEdit()
        self.case = QCheckBox("&Match case")
        form = QFormLayout()
        form.addRow("&Find:", self.find_text)
        form.addRow("Re&place with:", self.replace_text)
        form.addRow(self.case)
        row = QHBoxLayout()
        for label, slot in (
            ("Find &next", self.find_next),
            ("&Replace", self.replace),
            ("Replace &all", self.replace_all),
        ):
            button = QPushButton(label)
            button.clicked.connect(slot)
            row.addWidget(button)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(row)
        self.find_text.returnPressed.connect(self.find_next)

    def _flags(self) -> QTextDocument.FindFlag:
        return (
            QTextDocument.FindCaseSensitively
            if self.case.isChecked()
            else QTextDocument.FindFlag(0)
        )

    def find_next(self) -> bool:
        if self.editor is None or not self.find_text.text():
            return False
        if self.editor.find(self.find_text.text(), self._flags()):
            return True
        cursor = self.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        self.editor.setTextCursor(cursor)
        found = self.editor.find(self.find_text.text(), self._flags())
        if not found:
            self.message.emit(f"'{self.find_text.text()}' was not found")
        return found

    def _selection_matches(self) -> bool:
        selected = self.editor.textCursor().selectedText()
        wanted = self.find_text.text()
        return selected == wanted if self.case.isChecked() else selected.lower() == wanted.lower()

    def replace(self) -> None:
        if self.editor is None:
            return
        if self._selection_matches():
            self.editor.textCursor().insertText(self.replace_text.text())
        self.find_next()

    def replace_all(self) -> int:
        if self.editor is None or not self.find_text.text():
            return 0
        cursor = self.editor.textCursor()
        cursor.beginEditBlock()  # one undo step for the whole replace
        cursor.movePosition(cursor.MoveOperation.Start)
        self.editor.setTextCursor(cursor)
        count = 0
        while self.editor.find(self.find_text.text(), self._flags()):
            self.editor.textCursor().insertText(self.replace_text.text())
            count += 1
        cursor.endEditBlock()
        self.message.emit(f"{count} replaced")
        return count


class OptionsDialog(QDialog):
    def __init__(
        self,
        theme: str,
        font_size: int,
        show_welcome: bool,
        max_steps: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Options")
        self.theme = QComboBox()
        for key, label in CHOICES:
            self.theme.addItem(label, key)
        self.theme.setCurrentIndex(max(self.theme.findData(theme), 0))
        self.font_size = QSpinBox()
        self.font_size.setRange(6, 48)
        self.font_size.setValue(font_size)
        self.show_welcome = QCheckBox("Show the welcome window at start")
        self.show_welcome.setChecked(show_welcome)
        self.max_steps = QSpinBox()
        self.max_steps.setRange(1000, 1_000_000_000)
        self.max_steps.setSingleStep(100_000)
        self.max_steps.setValue(max_steps)
        form = QFormLayout()
        form.addRow("&Theme:", self.theme)
        form.addRow("Editor &font size:", self.font_size)
        form.addRow("&Step limit for Run:", self.max_steps)
        form.addRow(self.show_welcome)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About emu32")
        text = QLabel(
            f"<h3>emu32 {__version__}</h3>"
            "<p>A tool for learning 32-bit x86 assembly.</p>"
            f"<p>Author: {AUTHOR}</p>"
            f"<p>{LICENSE_TEXT}</p>"
            f'<p><a href="{REPOSITORY}">{REPOSITORY}</a></p>'
            "<p>emu32 is an independent project. It is not affiliated with EMU8086.</p>"
            "<p>Built with Unicorn, Keystone, Capstone and Qt for Python.</p>"
        )
        text.setOpenExternalLinks(True)
        text.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout = QVBoxLayout(self)
        layout.addWidget(text)
        layout.addWidget(buttons)


def read_source(path: str | Path) -> tuple[str, bool]:
    """Read a source file as UTF-8. Returns (text, fell_back): files that are not valid
    UTF-8 are read as Windows-1252 so old course files still open."""
    data = Path(path).read_bytes()
    try:
        return data.decode("utf-8-sig"), False
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace"), True


_INTEL_HINT = re.compile(r"^\s*section\s+\.", re.MULTILINE | re.IGNORECASE)


def looks_like_intel(text: str) -> bool:
    """Guess Intel/NASM syntax from a `section .text` style line."""
    return bool(_INTEL_HINT.search(text))
