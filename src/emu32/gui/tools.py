"""Converter, ASCII table and Calculator (section 8.5)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from emu32.gui.models import char_name
from emu32.gui.panels import fixed_font, make_table, set_row
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
    """Codes 0 to 255: decimal, hex and character (code page 437 above 127)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ASCII codes")
        self.table = make_table(["Dec", "Hex", "Char"], 256)
        for code in range(256):
            set_row(self.table, code, [str(code), f"{code:02X}", char_name(code)])
        note = QLabel("Codes 0 to 31 are control codes; 128 to 255 use code page 437.")
        note.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addWidget(note)
        self.resize(320, 520)


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
