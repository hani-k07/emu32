"""Converter, ASCII table and Calculator (section 8.5)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from emu32.gui import theme
from emu32.gui.models import char_name
from emu32.gui.panels import fixed_font, make_table
from emu32.numbers import BASES, NumberError, calculate, fits, parse, views


def _value_labels(form: QFormLayout) -> dict[str, QLabel]:
    labels = {}
    for key, title in (
        ("hex", "Hexadecimal:"),
        ("dec_unsigned", "Decimal, unsigned:"),
        ("dec_signed", "Decimal, signed:"),
        ("oct", "Octal:"),
        ("bin", "Binary:"),
    ):
        label = QLabel()
        label.setFont(fixed_font())
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow(title, label)
        labels[key] = label
    return labels


def _show(labels: dict[str, QLabel], value: int | None, bits: int) -> None:
    if value is None:
        for label in labels.values():
            label.setText("")
        return
    v = views(value, bits)
    labels["hex"].setText(v.hexadecimal)
    labels["dec_unsigned"].setText(str(v.unsigned))
    labels["dec_signed"].setText(str(v.signed))
    labels["oct"].setText(v.octal)
    labels["bin"].setText(v.binary)


class ConverterDialog(QDialog):
    """Type a number in one base; see it in all bases at 8, 16 or 32 bits."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Converter")
        self.value = QLineEdit()
        self.value.setFont(fixed_font())
        self.base = QComboBox()
        for name, title in (("dec", "Decimal"), ("hex", "Hexadecimal"), ("bin", "Binary"),
                            ("oct", "Octal")):  # fmt: skip
            self.base.addItem(title, name)
        self.bits = QComboBox()
        for bits in (8, 16, 32):
            self.bits.addItem(f"{bits} bits", bits)
        self.bits.setCurrentIndex(2)
        self.message = QLabel()
        form = QFormLayout()
        form.addRow("&Number:", self.value)
        form.addRow("&Typed in:", self.base)
        form.addRow("&Size:", self.bits)
        self.labels = _value_labels(form)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.message)
        self.value.textChanged.connect(self.update_views)
        self.base.currentIndexChanged.connect(self.update_views)
        self.bits.currentIndexChanged.connect(self.update_views)

    def update_views(self) -> None:
        bits = self.bits.currentData()
        text = self.value.text()
        self.message.setText("")
        if not text.strip():
            _show(self.labels, None, bits)
            return
        try:
            value = parse(text, BASES[self.base.currentData()])
        except NumberError as error:
            self.message.setText(str(error))
            _show(self.labels, None, bits)
            return
        if not fits(value, bits):
            self.message.setText(
                f"{value} does not fit in {bits} bits; showing the low {bits} bits"
            )
        _show(self.labels, value, bits)


class AsciiDialog(QDialog):
    """All 256 codes on one screen: 8 columns of 32, each cell "dec hex char".

    Control codes (0 to 31, space and 127) show their name in the accent color. Selecting a
    cell shows the code in every base below the grid.
    """

    ROWS = 32

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ASCII codes")
        columns = 256 // self.ROWS
        self.table = make_table(
            [f"{c * self.ROWS}-{c * self.ROWS + self.ROWS - 1}" for c in range(columns)], self.ROWS
        )
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(self.table.fontMetrics().height() + 2)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setSelectionBehavior(QTableWidget.SelectItems)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        for code in range(256):
            item = QTableWidgetItem(f"{code:3d} {code:02X} {char_name(code)}")
            item.setToolTip(f"{code} = {code:02X}h = {code:08b}b = {code:o}o")
            if code <= 32 or code == 127:
                item.setForeground(theme.color("accent"))
            self.table.setItem(code % self.ROWS, code // self.ROWS, item)
        self.detail = QLabel()
        self.detail.setFont(fixed_font())
        self.detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.table.currentCellChanged.connect(
            lambda row, column, *_: self.select(column * self.ROWS + row)
        )
        note = QLabel("Accent color: control codes. 128 to 255 use code page 437.")
        note.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addWidget(self.detail)
        layout.addWidget(note)
        self.table.setCurrentCell(65 % self.ROWS, 65 // self.ROWS)
        # Big enough to show all 256 codes without scrolling.
        table = self.table
        table.setMinimumSize(
            table.horizontalHeader().length() + 2 * table.frameWidth(),
            table.verticalHeader().length()
            + table.horizontalHeader().height()
            + 2 * table.frameWidth(),
        )

    def code_at(self, code: int) -> str:
        return self.table.item(code % self.ROWS, code // self.ROWS).text()

    def select(self, code: int) -> None:
        if 0 <= code < 256:
            self.detail.setText(
                f"{char_name(code)}   dec {code}   hex {code:02X}h   "
                f"bin {code:08b}b   oct {code:o}o"
            )


class CalculatorDialog(QDialog):
    """Integer expressions in any base, with bit operations."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calculator")
        self.expression = QLineEdit()
        self.expression.setFont(fixed_font())
        self.expression.setPlaceholderText("for example: (0FFh and 1010b) shl 2")
        self.bits = QComboBox()
        for bits in (8, 16, 32):
            self.bits.addItem(f"{bits} bits", bits)
        self.bits.setCurrentIndex(2)
        self.message = QLabel(
            "Numbers: 255, 0FFh, 0xFF, 1010b, 377o. Operators: + - * / mod and or xor not "
            "shl shr ( )."
        )
        self.message.setWordWrap(True)
        form = QFormLayout()
        form.addRow("&Expression:", self.expression)
        form.addRow("&Size:", self.bits)
        self.labels = _value_labels(form)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.message)
        self.expression.textChanged.connect(self.update_result)
        self.bits.currentIndexChanged.connect(self.update_result)

    def update_result(self) -> None:
        bits = self.bits.currentData()
        if not self.expression.text().strip():
            _show(self.labels, None, bits)
            return
        try:
            value = calculate(self.expression.text())
        except NumberError as error:
            self.message.setText(str(error))
            _show(self.labels, None, bits)
            return
        self.message.setText(f"Result: {value}")
        _show(self.labels, value, bits)


_FACTORIES = {"calculator": CalculatorDialog, "converter": ConverterDialog, "ascii": AsciiDialog}


def show_tool(owner: QWidget, name: str) -> QDialog:
    """Open a tool window, one per owner window, and bring it to the front."""
    tools = owner.__dict__.setdefault("_tool_windows", {})
    if name not in tools:
        tools[name] = _FACTORIES[name](owner)
    window = tools[name]
    window.show()
    window.raise_()
    window.activateWindow()
    return window
