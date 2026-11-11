"""Table models for the memory and disassembly panels.

Qt asks a model only for the rows on screen, so a 64 KB memory window stays cheap.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QFont

from emu32.gui import theme

CONTROL_NAMES = [
    "NULL", "SOH", "STX", "ETX", "EOT", "ENQ", "ACK", "BEL", "BS", "TAB", "LF", "VT", "FF",
    "CR", "SO", "SI", "DLE", "DC1", "DC2", "DC3", "DC4", "NAK", "SYN", "ETB", "CAN", "EM",
    "SUB", "ESC", "FS", "GS", "RS", "US",
]  # fmt: skip
CHANGED_MARK = "*"

# Looked up once: reading Qt.DisplayRole and friends inside data(), which Qt calls for every
# visible cell and role on each repaint, made each call cost tens of microseconds.
DISPLAY = int(Qt.ItemDataRole.DisplayRole)
BACKGROUND = int(Qt.ItemDataRole.BackgroundRole)
FOREGROUND = int(Qt.ItemDataRole.ForegroundRole)
ALIGNMENT = int(Qt.ItemDataRole.TextAlignmentRole)
FONT = int(Qt.ItemDataRole.FontRole)
HANDLED = frozenset((DISPLAY, BACKGROUND, FOREGROUND, ALIGNMENT, FONT))
RIGHT = Qt.AlignRight | Qt.AlignVCenter


def char_name(value: int) -> str:
    """Printable character, or the name of a control code."""
    if value < 32:
        return CONTROL_NAMES[value]
    if value == 32:
        return "SPACE"
    if value == 127:
        return "DEL"
    return bytes([value]).decode("cp437")


_BOLD = QFont()
_BOLD.setBold(True)


class MemoryModel(QAbstractTableModel):
    HEADERS = ("", "Address", "Hex", "Dec", "Char")
    WINDOW = 0x1_0000

    def __init__(self, format_address: Callable[[int], str]) -> None:
        super().__init__()
        self.format_address = format_address
        self.start = 0
        self.values: list[int | None] = []
        self.previous: list[int | None] | None = None

    def show(self, start: int, values: list[int | None]) -> None:
        """New contents. Bytes that differ from what this window showed before are marked
        as changed; the comparison happens only for rows on screen."""
        if start == self.start and len(values) == len(self.values):
            self.previous, self.values = self.values, values
            if self.values:
                self.dataChanged.emit(self.index(0, 0), self.index(len(values) - 1, 4))
            return
        self.beginResetModel()
        self.start, self.values, self.previous = start, values, None
        self.endResetModel()

    def changed(self, row: int) -> bool:
        return self.previous is not None and self.previous[row] != self.values[row]

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self.values)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # noqa: N802
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if role not in HANDLED:
            return None
        row, column = index.row(), index.column()
        if role == DISPLAY:
            if column == 0:
                return CHANGED_MARK if self.changed(row) else ""
            if column == 1:
                return self.format_address(self.start + row)
            value = self.values[row]
            if value is None:
                return "--"
            return (f"{value:02X}", str(value), char_name(value))[column - 2]
        if role == BACKGROUND and self.changed(row):
            return theme.color("changed")
        if role == FOREGROUND and column == 1:
            return theme.color("text.muted")
        if role == ALIGNMENT and column in (2, 3):
            return RIGHT
        return None


class DisassemblyModel(QAbstractTableModel):
    # The instruction comes before the bytes, so a narrow panel never hides it.
    HEADERS = ("", "Line", "Address", "Instruction", "Bytes")

    def __init__(self, format_address: Callable[[int], str]) -> None:
        super().__init__()
        self.format_address = format_address
        self.rows: list[tuple[int, bytes, str, int | None]] = []
        self._row_by_address: dict[int, int] = {}
        self.current: int | None = None
        self.breakpoints: frozenset[int] = frozenset()
        self.uppercase = False

    def show(self, rows, current: int | None, breakpoints: frozenset[int]) -> None:
        if rows is not self.rows:
            self.beginResetModel()
            self.rows = rows
            self._row_by_address = {row[0]: i for i, row in enumerate(rows)}
            self.endResetModel()
        self.current, self.breakpoints = current, breakpoints
        if rows:
            self.dataChanged.emit(self.index(0, 0), self.index(len(rows) - 1, 4))

    def row_of(self, address: int | None) -> int | None:
        return self._row_by_address.get(address)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # noqa: N802
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.HEADERS[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if role not in HANDLED:
            return None
        address, data, text, line = self.rows[index.row()]
        current = address == self.current
        column = index.column()
        if role == DISPLAY:
            if column == 0:
                return ("B" if address in self.breakpoints else "") + (">" if current else "")
            if column == 1:
                return "" if line is None else str(line)
            if column == 2:
                return self.format_address(address)
            if column == 3:
                return text.upper() if self.uppercase else text
            return data.hex(" ").upper()
        if role == BACKGROUND and current:
            return theme.color("current-line")
        if role == FOREGROUND:
            if column == 0 and address in self.breakpoints:
                return theme.color("error")
            if column in (1, 2, 4):
                return theme.color("text.muted")
        if role == ALIGNMENT and column == 1:
            return RIGHT
        if role == FONT and current:
            return _BOLD
        return None
