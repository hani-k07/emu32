"""Program console: collected output and blocking input, shared between threads.

The emulator thread reads input and blocks until the user types it. The UI thread feeds text
and can cancel a pending read, which turns into a normal Stop.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

# DOS-era code page, so programs that print box-drawing bytes show what students expect.
ENCODING = "cp437"


class InputCancelled(Exception):  # noqa: N818 - control signal
    pass


class Console:
    def __init__(self) -> None:
        self._output: list[str] = []
        self._input = ""
        self._cancelled = False
        self._cond = threading.Condition()
        self.waiting = False
        # Optional callbacks, called from the emulator thread.
        self.on_output: Callable[[str], None] | None = None
        self.on_wait: Callable[[bool], None] | None = None

    # Output

    def write(self, text: str) -> None:
        # Carriage returns only matter with a line feed after them, so they are dropped.
        text = text.replace("\r", "")
        if not text:
            return
        self._output.append(text)
        if self.on_output:
            self.on_output(text)

    def write_bytes(self, data: bytes) -> None:
        self.write(data.decode(ENCODING))

    def output(self) -> str:
        return "".join(self._output)

    def clear(self) -> None:
        with self._cond:
            self._output.clear()
            self._input = ""
            self._cancelled = False

    # Input

    def feed(self, text: str) -> None:
        """Add typed text. A line ends with a newline."""
        with self._cond:
            self._input += text
            self._cancelled = False
            self._cond.notify_all()

    def cancel(self) -> None:
        """Wake a blocked read and make it raise InputCancelled."""
        with self._cond:
            self._cancelled = True
            self._cond.notify_all()

    def read_line(self) -> str:
        self._wait(lambda: "\n" in self._input)
        line, _, self._input = self._input.partition("\n")
        return line.rstrip("\r")

    def read_char(self) -> str:
        self._wait(lambda: bool(self._input))
        char, self._input = self._input[0], self._input[1:]
        return char

    def _wait(self, ready: Callable[[], bool]) -> None:
        with self._cond:
            if ready():
                return
            self._set_waiting(True)
            try:
                while not ready():
                    if self._cancelled:
                        self._cancelled = False
                        raise InputCancelled
                    self._cond.wait()
            finally:
                self._set_waiting(False)

    def _set_waiting(self, value: bool) -> None:
        self.waiting = value
        if self.on_wait:
            self.on_wait(value)
