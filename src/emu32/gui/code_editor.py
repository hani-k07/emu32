"""Source editor: line-number gutter with breakpoint, bookmark and error markers."""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFontDatabase,
    QPainter,
    QTextBlockUserData,
    QTextCursor,
    QTextFormat,
)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from emu32.gui import theme
from emu32.gui.highlighter import AsmHighlighter

MIN_FONT, MAX_FONT = 6, 48


class _Marks(QTextBlockUserData):
    """Markers stored on the text block, so they move with the line while editing."""

    def __init__(self) -> None:
        super().__init__()
        self.breakpoint = False
        self.bookmark = False


class _Gutter(QWidget):
    def __init__(self, editor: CodeEditor) -> None:
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt override
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        self.editor.paint_gutter(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override
        block = self.editor.cursorForPosition(event.position().toPoint()).block()
        self.editor.toggle_breakpoint(block.blockNumber() + 1)


class CodeEditor(QPlainTextEdit):
    breakpoints_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        font.setPointSize(11)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.error_lines: set[int] = set()
        self.highlighter = AsmHighlighter(self.document())
        self._gutter = _Gutter(self)
        self.blockCountChanged.connect(self._update_margin)
        self.updateRequest.connect(self._update_gutter)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self._update_margin()
        self._highlight_current_line()

    # Layout and painting

    def setFont(self, font) -> None:  # noqa: N802 - Qt override
        super().setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 8)
        if hasattr(self, "_gutter"):
            self._update_margin()

    def gutter_width(self) -> int:
        digits = max(3, len(str(self.blockCount())))
        marks = self.fontMetrics().height() * 2
        return marks + self.fontMetrics().horizontalAdvance("9") * digits + 8

    def _update_margin(self, *_args) -> None:
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _update_gutter(self, rect: QRect, dy: int) -> None:
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_margin()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        area = self.contentsRect()
        self._gutter.setGeometry(QRect(area.left(), area.top(), self.gutter_width(), area.height()))

    def paint_gutter(self, event) -> None:
        c = theme.colors()
        painter = QPainter(self._gutter)
        painter.fillRect(event.rect(), QColor(c.gutter))
        painter.setRenderHint(QPainter.Antialiasing)
        height = self.fontMetrics().height()
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        while block.isValid() and top <= event.rect().bottom():
            bottom = top + round(self.blockBoundingRect(block).height())
            if block.isVisible() and bottom >= event.rect().top():
                line = block.blockNumber() + 1
                marks = block.userData()
                size = height - 6
                if isinstance(marks, _Marks) and marks.breakpoint:
                    painter.setBrush(QColor(c.breakpoint))
                    painter.setPen(Qt.NoPen)
                    painter.drawEllipse(3, top + 3, size, size)
                if isinstance(marks, _Marks) and marks.bookmark:
                    painter.setBrush(QColor(c.bookmark))
                    painter.setPen(Qt.NoPen)
                    painter.drawRect(height + 3, top + 3, size // 2, size)
                if line in self.error_lines:
                    painter.setBrush(QColor(c.error))
                    painter.setPen(Qt.NoPen)
                    painter.drawRect(height + size // 2 + 5, top + 2, size // 2, height - 4)
                painter.setPen(QColor(c.gutter_text))
                painter.drawText(0, top, self._gutter.width() - 4, height, Qt.AlignRight, str(line))
            block = block.next()
            top = bottom

    def _highlight_current_line(self) -> None:
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor(theme.colors().current_line))
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])

    def refresh_theme(self) -> None:
        self.highlighter.refresh_colors()
        self._highlight_current_line()
        self._gutter.update()

    # Lines

    def current_line(self) -> int:
        return self.textCursor().blockNumber() + 1

    def go_to_line(self, line: int) -> None:
        block = self.document().findBlockByNumber(max(line, 1) - 1)
        if block.isValid():
            cursor = QTextCursor(block)
            self.setTextCursor(cursor)
            self.centerCursor()
            self.setFocus()

    def set_error_lines(self, lines: set[int]) -> None:
        self.error_lines = set(lines)
        self._gutter.update()

    def zoom(self, steps: int) -> None:
        font = self.font()
        font.setPointSize(min(MAX_FONT, max(MIN_FONT, font.pointSize() + steps)))
        self.setFont(font)

    # Breakpoints and bookmarks

    def _marks(self, line: int) -> _Marks | None:
        block = self.document().findBlockByNumber(line - 1)
        if not block.isValid():
            return None
        if not isinstance(block.userData(), _Marks):
            block.setUserData(_Marks())
        return block.userData()

    def _lines_where(self, attribute: str) -> list[int]:
        lines, block = [], self.document().firstBlock()
        while block.isValid():
            marks = block.userData()
            if isinstance(marks, _Marks) and getattr(marks, attribute):
                lines.append(block.blockNumber() + 1)
            block = block.next()
        return lines

    def breakpoint_lines(self) -> list[int]:
        return self._lines_where("breakpoint")

    def toggle_breakpoint(self, line: int | None = None) -> None:
        marks = self._marks(line or self.current_line())
        if marks is not None:
            marks.breakpoint = not marks.breakpoint
            self._gutter.update()
            self.breakpoints_changed.emit()

    def bookmark_lines(self) -> list[int]:
        return self._lines_where("bookmark")

    def toggle_bookmark(self, line: int | None = None) -> None:
        marks = self._marks(line or self.current_line())
        if marks is not None:
            marks.bookmark = not marks.bookmark
            self._gutter.update()

    def clear_bookmarks(self) -> None:
        for line in self.bookmark_lines():
            self._marks(line).bookmark = False
        self._gutter.update()

    def next_bookmark(self, backwards: bool = False) -> None:
        lines = self.bookmark_lines()
        if not lines:
            return
        here = self.current_line()
        if backwards:
            target = next((n for n in reversed(lines) if n < here), lines[-1])
        else:
            target = next((n for n in lines if n > here), lines[0])
        self.go_to_line(target)
