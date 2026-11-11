"""Panels of the emulator window. Changes get a text marker (*) as well as a color."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from emu32.cpu_mode import CpuMode
from emu32.gui import theme
from emu32.gui.code_editor import CodeEditor
from emu32.gui.models import CHANGED_MARK

FLAG_MEANINGS = {
    "CF": "carry",
    "PF": "parity",
    "AF": "auxiliary carry",
    "ZF": "zero",
    "SF": "sign",
    "DF": "direction",
    "OF": "overflow",
    "IF": "interrupt enable",
}


def fixed_font():
    return QFontDatabase.systemFont(QFontDatabase.FixedFont)


def count_text(steps: int, approximate: bool) -> str:
    """Long runs skip exact counting, so their count is a lower bound (D65)."""
    return f"at least {steps:,}" if approximate else f"{steps:,}"


def make_table(headers: list[str], rows: int = 0) -> QTableWidget:
    table = QTableWidget(rows, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(table.fontMetrics().height() + 6)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setFont(fixed_font())
    table.setAlternatingRowColors(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    table.horizontalHeader().setStretchLastSection(True)
    return table


def fit_columns(view: QAbstractItemView, widths_in_chars: list[int]) -> int:
    """Set column widths from the font instead of measuring the contents, which would
    read every row on each refresh. Returns the total width, for a minimum panel width."""
    header = view.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.Interactive)
    header.setStretchLastSection(True)
    char = view.fontMetrics().horizontalAdvance("0")
    header_metrics = header.fontMetrics()
    model = view.model()
    total = 0
    for column, chars in enumerate(widths_in_chars):
        # Never narrower than the header label, so titles such as "Register" are not cut.
        title = str(model.headerData(column, Qt.Horizontal) or "")
        width = max(char * chars, header_metrics.horizontalAdvance(title)) + 20
        view.setColumnWidth(column, width)
        total += width
    return total + view.verticalScrollBar().sizeHint().width() + 4


def set_row(table: QTableWidget, row: int, values: list[str], changed: bool = False) -> None:
    for column, value in enumerate(values):
        item = table.item(row, column)
        if item is None:
            item = QTableWidgetItem()
            table.setItem(row, column, item)
        item.setText(value)
        item.setData(Qt.BackgroundRole, theme.color("changed") if changed else None)


class RegistersPanel(QWidget):
    edit_requested = Signal(str)

    def __init__(self, mode: CpuMode) -> None:
        super().__init__()
        self.mode = mode
        self.table = make_table(
            ["", "Register", "Value", "16-bit", "High", "Low"], len(mode.registers)
        )
        self.table.setToolTip("Double-click a register to change it while the program is paused.")
        # Never narrower than its columns, so High and Low are not cut off.
        self.table.setMinimumWidth(fit_columns(self.table, [1, 6, 8, 4, 2, 2]))
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.cellDoubleClicked.connect(
            lambda row, _c: self.edit_requested.emit(self.mode.registers[row])
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)

    def refresh(self, registers: dict[str, int], before: dict[str, int]) -> None:
        if not registers:
            return
        parts = self.mode.split_registers(registers)
        for row, name in enumerate(self.mode.registers):
            changed = before.get(name, registers[name]) != registers[name]
            short = name[1:]  # EAX -> AX, ESI -> SI
            sixteen = f"{parts[short]:04X}" if short in parts else ""
            high = f"{parts[short[0] + 'H']:02X}" if short[0] + "H" in parts else ""
            low = f"{parts[short[0] + 'L']:02X}" if short[0] + "L" in parts else ""
            set_row(
                self.table,
                row,
                [
                    CHANGED_MARK if changed else "",
                    name,
                    f"{registers[name]:08X}",
                    sixteen,
                    high,
                    low,
                ],
                changed,
            )


class FlagsPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.table = make_table(["", "Flag", "Value", "Meaning"], len(FLAG_MEANINGS))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)

    def refresh(self, flags: dict[str, int], before: dict[str, int]) -> None:
        for row, (name, meaning) in enumerate(FLAG_MEANINGS.items()):
            changed = before.get(name, flags.get(name)) != flags.get(name)
            set_row(
                self.table,
                row,
                [CHANGED_MARK if changed else "", name, str(flags.get(name, 0)), meaning],
                changed,
            )


class StackPanel(QWidget):
    """Dwords around ESP, with ESP and EBP marked."""

    ABOVE, BELOW = 6, 18  # rows above ESP (pushed later) and from ESP upward

    def __init__(self, mode: CpuMode) -> None:
        super().__init__()
        self.mode = mode
        self.table = make_table(["", "Address", "Value", "Decimal"], self.ABOVE + self.BELOW)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)

    def refresh(self, registers: dict[str, int], read_bytes) -> None:
        if not registers:
            return
        size = self.mode.word_size
        sp, bp = registers[self.mode.stack_pointer], registers.get("EBP", 0)
        region = self.mode.region("stack")
        first = sp - self.ABOVE * size
        for row in range(self.table.rowCount()):
            address = first + row * size
            if not region.start <= address <= region.end - size:
                set_row(self.table, row, ["", "", "", ""])
                continue
            data = read_bytes(address, size)
            value = int.from_bytes(bytes(b or 0 for b in data), "little")
            marks = " ".join(n for n, a in (("ESP", sp), ("EBP", bp)) if a == address)
            signed = value - (1 << 8 * size) if value >> (8 * size - 1) else value
            set_row(
                self.table,
                row,
                [marks, self.mode.format_address(address), f"{value:08X}", str(signed)],
                address == sp,
            )


class VarsPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.table = make_table(["", "Name", "Address", "Type", "Decimal", "Hex"])
        self._previous: dict[str, int] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)

    def refresh(self, variables, format_address) -> None:
        self.table.setRowCount(len(variables))
        for row, (symbol, value) in enumerate(variables):
            changed = self._previous.get(symbol.name, value) != value
            width = symbol.size * 2
            set_row(
                self.table,
                row,
                [
                    CHANGED_MARK if changed else "",
                    symbol.name,
                    format_address(symbol.address),
                    f"{symbol.type_name} x{symbol.count}" if symbol.count > 1 else symbol.type_name,
                    str(value),
                    f"{value & ((1 << 8 * symbol.size) - 1):0{width}X}",
                ],
                changed,
            )
        self._previous = {symbol.name: value for symbol, value in variables}

    def reset(self) -> None:
        self._previous = {}


class ScreenPanel(QWidget):
    """Program output, and a line for typed input."""

    submitted = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(fixed_font())
        self.input = QLineEdit()
        self.input.setPlaceholderText("Type input for the program and press Enter")
        self.send = QPushButton("&Send")
        self.status = QLabel("")
        row = QHBoxLayout()
        row.addWidget(self.input)
        row.addWidget(self.send)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.output)
        layout.addLayout(row)
        layout.addWidget(self.status)
        self.input.returnPressed.connect(self._submit)
        self.send.clicked.connect(self._submit)

    def _submit(self) -> None:
        text = self.input.text()
        self.input.clear()
        self.submitted.emit(text)

    def set_text(self, text: str) -> None:
        if self.output.toPlainText() != text:
            self.output.setPlainText(text)
            self.output.moveCursor(self.output.textCursor().MoveOperation.End)

    def append(self, text: str) -> None:
        cursor = self.output.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self.output.setTextCursor(cursor)

    def set_waiting(self, waiting: bool) -> None:
        self.status.setText("Waiting for input" if waiting else "")
        if waiting:
            self.input.setFocus()


class AuxPanel(QWidget):
    """Execution trace of single steps and the instruction counter."""

    def __init__(self) -> None:
        super().__init__()
        self.counter = QLabel("Instructions executed: 0")
        self.trace = QListWidget()
        self.trace.setFont(fixed_font())
        note = QLabel("The trace lists single steps; Run does not record them.")
        note.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.counter)
        layout.addWidget(self.trace)
        layout.addWidget(note)

    def refresh(self, steps: int, records, format_address, approximate: bool = False) -> None:
        self.counter.setText(f"Instructions executed: {count_text(steps, approximate)}")
        lines = [
            f"{format_address(r.address)}  {r.text:<28} line {r.line if r.line else '-'}"
            for r in records
        ]
        if [self.trace.item(i).text() for i in range(self.trace.count())] != lines:
            self.trace.clear()
            self.trace.addItems(lines)
            self.trace.scrollToBottom()


class DebugPanel(QWidget):
    """Breakpoint list and watch expressions."""

    remove_breakpoint = Signal(int)
    watches_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.watches: list[str] = []
        self.breakpoints = QListWidget()
        remove_bp = QPushButton("Remove &breakpoint")
        remove_bp.clicked.connect(self._remove_breakpoint)
        self.watch_table = make_table(["Expression", "Hex", "Decimal"])
        self.watch_input = QLineEdit()
        self.watch_input.setPlaceholderText("Add a watch, for example: eax + 1, total, [esi]")
        self.watch_input.returnPressed.connect(self._add_watch)
        remove_watch = QPushButton("Remove &watch")
        remove_watch.clicked.connect(self._remove_watch)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Breakpoints (line):"))
        layout.addWidget(self.breakpoints)
        layout.addWidget(remove_bp)
        layout.addWidget(QLabel("Watches:"))
        layout.addWidget(self.watch_table)
        row = QHBoxLayout()
        row.addWidget(self.watch_input)
        row.addWidget(remove_watch)
        layout.addLayout(row)

    def _remove_breakpoint(self) -> None:
        item = self.breakpoints.currentItem()
        if item is not None:
            self.remove_breakpoint.emit(int(item.data(Qt.UserRole)))

    def _add_watch(self) -> None:
        text = self.watch_input.text().strip()
        if text:
            self.watches.append(text)
            self.watch_input.clear()
            self.watches_changed.emit()

    def _remove_watch(self) -> None:
        row = self.watch_table.currentRow()
        if 0 <= row < len(self.watches):
            del self.watches[row]
            self.watches_changed.emit()

    def refresh(self, breakpoint_lines, watch_values) -> None:
        self.breakpoints.clear()
        for line in sorted(breakpoint_lines):
            self.breakpoints.addItem(f"line {line}")
            self.breakpoints.item(self.breakpoints.count() - 1).setData(Qt.UserRole, line)
        self.watch_table.setRowCount(len(watch_values))
        for row, (expression, value) in enumerate(watch_values):
            if isinstance(value, int):
                set_row(
                    self.watch_table, row, [expression, f"{value & 0xFFFF_FFFF:08X}", str(value)]
                )
            else:
                set_row(self.watch_table, row, [expression, value, ""])


class SourcePanel(CodeEditor):
    """Read-only source with the current line selected and breakpoints in the gutter."""

    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)

    def set_source(self, text: str, breakpoint_lines) -> None:
        self.blockSignals(True)
        self.setPlainText(text)
        for line in breakpoint_lines:
            self.toggle_breakpoint(line)
        self.blockSignals(False)

    def sync_breakpoints(self, lines) -> None:
        current = set(self.breakpoint_lines())
        self.blockSignals(True)
        for line in current ^ set(lines):
            self.toggle_breakpoint(line)
        self.blockSignals(False)

    def show_line(self, line: int | None) -> None:
        if line:
            self.go_to_line(line, focus=False)
