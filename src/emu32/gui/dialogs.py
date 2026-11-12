"""Welcome, new file, find and replace, options and about dialogs."""

from __future__ import annotations

import platform
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
    QGroupBox,
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
from emu32.gui.panels import fixed_font
from emu32.gui.templates import TEMPLATES
from emu32.gui.theme import CHOICES
from emu32.gui.theme.tokens import TYPE_SCALE

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


def component_versions() -> list[tuple[str, str, str]]:
    """(name, version, license) for each engine and library inside emu32."""

    def version(module: str) -> str:
        try:
            return str(__import__(module).__version__)
        except Exception:  # noqa: BLE001 - a missing version must never stop the dialog
            return ""

    return [
        ("Unicorn (emulator)", version("unicorn"), "GPL-2.0"),
        ("Keystone (assembler)", version("keystone"), "GPL-2.0"),
        ("Capstone (disassembler)", version("capstone"), "BSD-3-Clause"),
        ("Qt for Python", version("PySide6"), "LGPL-3.0 / GPL"),
        ("Python", platform.python_version(), "PSF-2.0"),
    ]


class AboutDialog(QDialog):
    """Name and version, the license, the parts emu32 is built from, and where to find it."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About emu32")
        name = QLabel("emu32")
        font = name.font()
        font.setPointSize(TYPE_SCALE[-1] + 8)
        font.setBold(True)
        name.setFont(font)
        version = QLabel(f"version {__version__}")
        version.setFont(fixed_font())
        subtitle = QLabel("32-bit x86 assembly learning tool")
        for label in (name, version, subtitle):
            label.setAlignment(Qt.AlignCenter)

        license_box = QGroupBox("License")
        license_text = QLabel(
            f"{LICENSE_TEXT}<br>Use, copy, change and share it freely. "
            "No registration or internet connection is needed."
        )
        license_text.setWordWrap(True)
        license_text.setAlignment(Qt.AlignCenter)
        QVBoxLayout(license_box).addWidget(license_text)

        built_box = QGroupBox("Built with")
        grid = QGridLayout(built_box)
        grid.setHorizontalSpacing(16)
        for row, (part, ver, lic) in enumerate(component_versions()):
            cells = [QLabel(part), QLabel(ver), QLabel(lic)]
            cells[1].setFont(fixed_font())
            cells[2].setObjectName("muted")
            for column, cell in enumerate(cells):
                grid.addWidget(cell, row, column)
        notices = QLabel("Full license texts: THIRD_PARTY_NOTICES.md, in the program folder.")
        notices.setObjectName("muted")
        notices.setWordWrap(True)
        grid.addWidget(notices, len(component_versions()), 0, 1, 3)

        copyright_ = QLabel(
            f"Copyright (C) 2026 {AUTHOR}<br>"
            "emu32 is an independent project, not affiliated with EMU8086."
        )
        copyright_.setAlignment(Qt.AlignCenter)
        copyright_.setWordWrap(True)
        link = QLabel(f'<a href="{REPOSITORY}">{REPOSITORY.removeprefix("https://")}</a>')
        link.setOpenExternalLinks(True)
        link.setAlignment(Qt.AlignCenter)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(8)
        for widget in (name, version, subtitle):
            layout.addWidget(widget)
        layout.addSpacing(8)
        layout.addWidget(license_box)
        layout.addWidget(built_box)
        layout.addWidget(copyright_)
        layout.addWidget(link)
        layout.addWidget(buttons)
        # A minimum, not a fixed width: a wider system font must not cut the text off.
        self.setMinimumWidth(480)
        # Wrapped text needs more height at this width than the default size hint gives.
        self.resize(480, max(self.sizeHint().height(), layout.totalHeightForWidth(480)))


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
