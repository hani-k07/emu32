"""Table models for the memory and disassembly panels.

Qt asks a model only for the rows on screen, so a 64 KB memory window stays cheap.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor, QFont

from emu32.gui import theme

CONTROL_NAMES = [
    "NULL", "SOH", "STX", "ETX", "EOT", "ENQ", "ACK", "BEL", "BS", "TAB", "LF", "VT", "FF",
    "CR", "SO", "SI", "DLE", "DC1", "DC2", "DC3", "DC4", "NAK", "SYN", "ETB", "CAN", "EM",
    "SUB", "ESC", "FS", "GS", "RS", "US",
]  # fmt: skip
CHANGED_MARK = "*"


def char_name(value: int) -> str:
    """Printable character, or the name of a control code."""
    if value < 32:
        return CONTROL_NAMES[value]
    if value == 32:
        return "SPACE"
    if value == 127:
        return "DEL"
    return bytes([value]).decode("cp437")


class MemoryModel(QAbstractTableModel):
    HEADERS = ("", "Address", "Hex", "Dec", "Char")
    WINDOW = 0x1_0000

    def __init__(self, format_address: Callable[[int], str]) -> None:
        super().__init__()
        self.format_address = format_address
        self.start = 0
        self.values: list[int | None] = []
        self.changed: set[int] = set()

    def show(self, start: int, values: list[int | None]) -> None:
        """New contents. Bytes that differ from the previous contents of the same window are
        marked as changed."""
        if start == self.start and len(values) == len(self.values):
            self.changed = {
                i for i, (a, b) in enumerate(zip(values, self.values, strict=True)) if a != b
            }
            self.values = values
            if self.values:
                self.dataChanged.emit(self.index(0, 0), self.index(len(values) - 1, 4))
            return
        self.beginResetModel()
        self.start, self.values, self.changed = start, values, set()
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self.values)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # noqa: N802
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        row, column = index.row(), index.column()
        value = self.values[row]
        if role == Qt.DisplayRole:
            if column == 0:
                return CHANGED_MARK if row in self.changed else ""
            if column == 1:
                return self.format_address(self.start + row)
            if value is None:
                return "--"
            return (f"{value:02X}", str(value), char_name(value))[column - 2]
        if role == Qt.BackgroundRole and row in self.changed:
            return QColor(theme.colors().changed)
        if role == Qt.TextAlignmentRole and column in (2, 3):
            return Qt.AlignRight | Qt.AlignVCenter
        return None


class DisassemblyModel(QAbstractTableModel):
    HEADERS = ("", "Address", "Bytes", "Instruction", "Line")

    def __init__(self, format_address: Callable[[int], str]) -> None:
        super().__init__()
        self.format_address = format_address
        self.rows: list[tuple[int, bytes, str, int | None]] = []
        self.current: int | None = None
        self.breakpoints: frozenset[int] = frozenset()
        self.uppercase = False

    def show(self, rows, current: int | None, breakpoints: frozenset[int]) -> None:
        if rows is not self.rows:
            self.beginResetModel()
            self.rows = rows
            self.endResetModel()
        self.current, self.breakpoints = current, breakpoints
        if rows:
            self.dataChanged.emit(self.index(0, 0), self.index(len(rows) - 1, 4))

    def row_of(self, address: int | None) -> int | None:
        return next((i for i, row in enumerate(self.rows) if row[0] == address), None)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # noqa: N802
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        address, data, text, line = self.rows[index.row()]
        current = address == self.current
        if role == Qt.DisplayRole:
            column = index.column()
            if column == 0:
                return ("B" if address in self.breakpoints else "") + (">" if current else "")
            if column == 1:
                return self.format_address(address)
            if column == 2:
                return data.hex(" ").upper()
            if column == 3:
                return text.upper() if self.uppercase else text
            return "" if line is None else str(line)
        if role == Qt.BackgroundRole and current:
            return QColor(theme.colors().current_line)
        if role == Qt.ForegroundRole and index.column() == 0 and address in self.breakpoints:
            return QColor(theme.colors().breakpoint)
        if role == Qt.FontRole and current:
            font = QFont()
            font.setBold(True)
            return font
        return None
