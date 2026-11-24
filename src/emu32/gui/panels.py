"""Panels of the emulator window. Changes get a text marker (*) as well as a color."""

from __future__ import annotations

import struct

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
from emu32.emulator.core import extended_to_float
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


def value_texts(symbol, value: int) -> tuple[str, str]:
    """Decimal and hex text of a variable's first element. REAL variables show their
    number; a structure shows its first bytes."""
    raw = (value & ((1 << 8 * symbol.size) - 1)).to_bytes(symbol.size, "little")
    if symbol.kind in ("real4", "real8", "real10"):
        if symbol.size == 10:
            number = extended_to_float(int.from_bytes(raw[:8], "little"), raw[8] | raw[9] << 8)
        else:
            number = struct.unpack("<f" if symbol.size == 4 else "<d", raw)[0]
        return f"{number:.10g}", raw[::-1].hex().upper()
    if symbol.size > 8:
        return "", raw[:8].hex(" ").upper() + " ..."
    return str(value), raw[::-1].hex().upper()


def refit_columns(view: QAbstractItemView) -> int:
    """Set the column widths again after the font changed (zoom, projector mode), so
    titles and values are not cut off. Returns the new total width."""
    chars = view.property("fit_chars")
    if not chars:
        return 0
    view.verticalHeader().setDefaultSectionSize(view.fontMetrics().height() + 6)
    return fit_columns(view, list(chars))


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
    view.setProperty("fit_chars", list(widths_in_chars))  # so refit_columns can redo it
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
        self.table = make_table(["", "Register", "", "", "", ""], len(mode.registers))
        self.table.setToolTip("Double-click a register to change it while the program is paused.")
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.cellDoubleClicked.connect(
            lambda row, _c: self.edit_requested.emit(self.mode.registers[row])
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        self.set_mode(mode)

    def set_mode(self, mode: CpuMode) -> None:
        """Rows and columns for a program model: 32-bit registers with their parts (flat),
        or 8086 registers with their bytes and the 386's 32-bit register (COM, EXE)."""
        self.mode = mode
        self.table.clearContents()
        self.table.setRowCount(len(mode.registers))
        if mode.is_16bit:
            columns = ["", "Register", "16-bit", "Bits 15-8", "Bits 7-0", "32-bit"]
            tips = (
                "The 8086 register, for example AX",
                "The high byte, for example AH (AX, BX, CX and DX only)",
                "The low byte, for example AL (AX, BX, CX and DX only)",
                "The whole 32-bit register it is part of, for example EAX. COM and EXE "
                "programs may use 32-bit registers, as on a 386",
            )
            widths = [1, 6, 4, 2, 2, 8]
        else:
            columns = ["", "Register", "32-bit", "Low 16", "Bits 15-8", "Bits 7-0"]
            # The last three columns are parts of the same register, not separate registers.
            tips = (
                "The whole register, for example EAX",
                "The low 16 bits of the register, for example AX (part of EAX)",
                "Bits 15 to 8, the high byte of AX, for example AH (EAX, EBX, ECX and EDX only)",
                "Bits 7 to 0, the low byte of AX, for example AL (EAX, EBX, ECX and EDX only)",
            )
            widths = [1, 6, 8, 4, 2, 2]
        self.table.setHorizontalHeaderLabels(columns)
        for column, tip in enumerate(tips, start=2):
            self.table.horizontalHeaderItem(column).setToolTip(tip)
        # Never narrower than its columns, so the last ones are not cut off.
        self.table.setMinimumWidth(fit_columns(self.table, widths))

    def refresh(self, registers: dict[str, int], before: dict[str, int]) -> None:
        if not registers:
            return
        parts = self.mode.split_registers(registers)
        if self.mode.is_16bit:
            self._refresh_16(registers, before, parts)
            return
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

    def _refresh_16(
        self, registers: dict[str, int], before: dict[str, int], parts: dict[str, int]
    ) -> None:
        for row, name in enumerate(self.mode.registers):
            wide = f"E{name}" if f"E{name}" in registers else None
            changed = any(
                before.get(key, registers[key]) != registers[key] for key in (name, wide) if key
            )
            high, low = f"{name[0]}H", f"{name[0]}L"
            set_row(
                self.table,
                row,
                [
                    CHANGED_MARK if changed else "",
                    name,
                    f"{registers[name]:04X}",
                    f"{parts[high]:02X}" if high in parts and name.endswith("X") else "",
                    f"{parts[low]:02X}" if low in parts and name.endswith("X") else "",
                    f"{registers[wide]:08X}" if wide else "",
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


class FpuPanel(QWidget):
    """The x87 register stack, ST(0) at the top, and the status word."""

    def __init__(self) -> None:
        super().__init__()
        self.table = make_table(["", "Register", "Value"], 8)
        self.status = QLabel()
        self.status.setFont(fixed_font())
        self.status.setToolTip("TOP: which physical register is ST(0). C3 C2 C0: compare result.")
        self._previous: list[float | None] = [None] * 8
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        layout.addWidget(self.status)

    def refresh(self, stack: list[float | None], status: int) -> None:
        for row, value in enumerate(stack):
            changed = value != self._previous[row]
            text = "empty" if value is None else f"{value:.10g}"
            set_row(self.table, row, [CHANGED_MARK if changed else "", f"ST({row})", text], changed)
        self._previous = list(stack)
        top = (status >> 11) & 7
        c0, c2, c3 = (status >> 8) & 1, (status >> 10) & 1, (status >> 14) & 1
        self.status.setText(f"Status {status:04X}  TOP={top}  C3={c3} C2={c2} C0={c0}")

    def reset(self) -> None:
        self._previous = [None] * 8


class StackPanel(QWidget):
    """Words (COM, EXE) or dwords (flat) around the stack pointer, with SP and BP marked."""

    ABOVE, BELOW = 6, 18  # rows above ESP (pushed later) and from ESP upward

    def __init__(self, mode: CpuMode) -> None:
        super().__init__()
        self.mode = mode
        self.table = make_table(["", "Address", "Value", "Decimal"], self.ABOVE + self.BELOW)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)

    def set_mode(self, mode: CpuMode) -> None:
        self.mode = mode
        self.table.clearContents()

    def refresh(self, registers: dict[str, int], read_bytes) -> None:
        if not registers:
            return
        mode = self.mode
        size = mode.word_size
        sp, bp = registers[mode.stack_pointer], registers.get(mode.base_pointer, 0)
        # The stack grows down from stack_top; the flat model gives it its own region.
        low = 0 if mode.is_16bit else mode.region("stack").start
        first = sp - self.ABOVE * size
        for row in range(self.table.rowCount()):
            address = first + row * size
            if not low <= address <= mode.stack_top - size:
                set_row(self.table, row, ["", "", "", ""])
                continue
            data = read_bytes(address, size)
            value = int.from_bytes(bytes(b or 0 for b in data), "little")
            marks = " ".join(
                n for n, a in ((mode.stack_pointer, sp), (mode.base_pointer, bp)) if a == address
            )
            signed = value - (1 << 8 * size) if value >> (8 * size - 1) else value
            set_row(
                self.table,
                row,
                [marks, mode.format_address(address), f"{value:0{2 * size}X}", str(signed)],
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
            decimal, hex_text = value_texts(symbol, value)
            set_row(
                self.table,
                row,
                [
                    CHANGED_MARK if changed else "",
                    symbol.name,
                    format_address(symbol.address),
                    f"{symbol.type_name} x{symbol.count}" if symbol.count > 1 else symbol.type_name,
                    decimal,
                    hex_text,
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
