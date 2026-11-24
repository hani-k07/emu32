"""Change highlighting that fades out (spec 10.6).

A value changed by the last step gets the `changed` background, which fades out over
DURATION_MS; the `*` marker beside it stays, so the change never depends on color alone.
With "Reduce motion" (Options) the background stays until the next step instead.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidgetItem

from emu32.gui import theme

DURATION_MS = 600
TICK_MS = 40
reduce_motion = False


class _Fader(QObject):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[QTableWidgetItem] = []
        self.models: list = []  # table models with a fade_tick() method
        self.started = 0.0
        self.pending = False
        self.timer = QTimer(self)
        self.timer.setInterval(TICK_MS)
        self.timer.timeout.connect(self._tick)

    def color(self) -> QColor | None:
        """The highlight now: full right after a step, then fading, then none."""
        full = theme.color("changed")
        if reduce_motion or self.pending:
            return full
        if not self.timer.isActive():
            return None  # faded out
        left = 1 - (time.monotonic() - self.started) * 1000 / DURATION_MS
        if left <= 0:
            return None
        faded = QColor(full)
        faded.setAlphaF(left)
        return faded

    def mark(self, item: QTableWidgetItem) -> None:
        self.items.append(item)
        self.restart()

    def restart(self) -> None:
        """A new step was shown: start the fade once this round of updates is done."""
        if reduce_motion or self.pending:
            return
        self.pending = True
        QTimer.singleShot(0, self._begin)

    def _begin(self) -> None:
        self.pending = False
        self.started = time.monotonic()
        self.timer.start()

    def _tick(self) -> None:
        color = self.color()
        alive = []
        for item in self.items:
            try:
                item.setData(Qt.BackgroundRole, color)
                alive.append(item)
            except RuntimeError:  # the table dropped the item
                pass
        self.items = alive
        for model in list(self.models):
            try:
                model.fade_tick()
            except RuntimeError:  # its window was closed
                self.models.remove(model)
        if color is None:
            self.timer.stop()
            self.items = []


_fader: _Fader | None = None


def fader() -> _Fader:
    global _fader
    if _fader is None:
        _fader = _Fader()
    return _fader
