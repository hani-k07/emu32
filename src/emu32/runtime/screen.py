"""The 80 x 25 text screen (spec 8.3): characters with color attributes and a cursor.

No Qt here; the Screen panel draws a snapshot. Output goes through `teletype`, which treats
CR, LF, backspace, tab and BEL as the BIOS and DOS do and scrolls at the bottom. The
`int 10h` services place characters and the cursor directly.

Step back: the first change in a step saves the screen as it was (`begin_step` /
`end_step`), so only steps that changed the screen keep a copy.
"""

from __future__ import annotations

import itertools
import threading

COLUMNS, ROWS = 80, 25
DEFAULT_ATTRIBUTE = 0x07  # light gray on black
BLANK = (" ", DEFAULT_ATTRIBUTE)
# Unique across screens, so a panel notices a new screen (after a reload) as a change.
_VERSIONS = itertools.count(1)


class TextScreen:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.cells: list[tuple[str, int]] = [BLANK] * (COLUMNS * ROWS)
        self.row = self.column = 0
        self.attribute = DEFAULT_ATTRIBUTE  # for new text (SetTextColor)
        self.version = next(_VERSIONS)  # changes whenever the screen does
        self._before: tuple | None = None
        self._recording = False
        # A line feed on a PC screen only moves down; DOS programs print CR LF. A Windows
        # console (flat programs) also returns to column 0. The session sets this per model.
        self.line_feed_returns = True

    # Snapshots

    def state(self) -> tuple:
        with self._lock:
            return self._state()

    def _state(self) -> tuple:
        return (tuple(self.cells), self.row, self.column, self.attribute)

    def restore(self, state: tuple) -> None:
        with self._lock:
            cells, self.row, self.column, self.attribute = state
            self.cells = list(cells)
            self.version = next(_VERSIONS)

    def begin_step(self) -> None:
        self._before, self._recording = None, True

    def end_step(self) -> tuple | None:
        """The screen before this step, if the step changed it."""
        before, self._before, self._recording = self._before, None, False
        return before

    def _changing(self) -> None:
        if self._recording and self._before is None:
            self._before = self._state()
        self.version = next(_VERSIONS)

    # Teletype output

    def teletype(self, text: str) -> None:
        with self._lock:
            self._changing()
            for char in text:
                self._put(char)

    def _put(self, char: str) -> None:
        if char == "\r":
            self.column = 0
        elif char == "\n":
            if self.line_feed_returns:
                self.column = 0
            self._line_feed()
        elif char == "\b":
            self.column = max(0, self.column - 1)
        elif char == "\t":
            for _ in range(8 - self.column % 8):
                self._put(" ")
        elif char == "\x07":
            pass  # BEL: no sound
        else:
            self.cells[self.row * COLUMNS + self.column] = (char, self.attribute)
            self.column += 1
            if self.column == COLUMNS:
                self.column = 0
                self._line_feed()

    def _line_feed(self) -> None:
        if self.row < ROWS - 1:
            self.row += 1
        else:
            self._scroll_up(1, 0, 0, ROWS - 1, COLUMNS - 1, DEFAULT_ATTRIBUTE)

    # int 10h services

    def clear(self, attribute: int = DEFAULT_ATTRIBUTE) -> None:
        with self._lock:
            self._changing()
            self.cells = [(" ", attribute)] * (COLUMNS * ROWS)
            self.row = self.column = 0

    def set_cursor(self, row: int, column: int) -> None:
        with self._lock:
            self._changing()
            self.row = min(max(row, 0), ROWS - 1)
            self.column = min(max(column, 0), COLUMNS - 1)

    def cursor(self) -> tuple[int, int]:
        return self.row, self.column

    def set_attribute(self, attribute: int) -> None:
        with self._lock:
            self._changing()
            self.attribute = attribute & 0xFF

    def write_repeated(self, char: str, attribute: int, count: int) -> None:
        """`int 10h/09h`: a character `count` times at the cursor, which does not move."""
        with self._lock:
            self._changing()
            start = self.row * COLUMNS + self.column
            for index in range(start, min(start + count, COLUMNS * ROWS)):
                self.cells[index] = (char, attribute)

    def write_at(self, row: int, column: int, text: str, attributes: list[int]) -> None:
        """`int 10h/13h`: text placed from (row, column), wrapping and scrolling like a
        teletype but with an attribute per character."""
        with self._lock:
            self._changing()
            self.row = min(max(row, 0), ROWS - 1)
            self.column = min(max(column, 0), COLUMNS - 1)
            saved = self.attribute
            for char, attribute in zip(text, attributes, strict=True):
                self.attribute = attribute
                self._put(char)
            self.attribute = saved

    def scroll_up(
        self, lines: int, top: int, left: int, bottom: int, right: int, attr: int
    ) -> None:
        """`int 10h/06h`: scroll a window up; 0 lines (or more than its height) clears it."""
        with self._lock:
            self._changing()
            self._scroll_up(lines, top, left, bottom, right, attr)

    def _scroll_up(
        self, lines: int, top: int, left: int, bottom: int, right: int, attr: int
    ) -> None:
        top, bottom = max(0, top), min(ROWS - 1, bottom)
        left, right = max(0, left), min(COLUMNS - 1, right)
        if top > bottom or left > right:
            return
        height = bottom - top + 1
        if lines == 0 or lines >= height:
            lines = height
        for row in range(top, bottom + 1):
            source = row + lines
            for column in range(left, right + 1):
                if source <= bottom:
                    self.cells[row * COLUMNS + column] = self.cells[source * COLUMNS + column]
                else:
                    self.cells[row * COLUMNS + column] = (" ", attr)

    def text(self) -> str:
        """The screen as plain lines, trailing spaces removed (for tests and copying)."""
        with self._lock:
            lines = [
                "".join(c for c, _a in self.cells[r * COLUMNS : (r + 1) * COLUMNS]).rstrip()
                for r in range(ROWS)
            ]
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)
