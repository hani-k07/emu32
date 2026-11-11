"""Runs Session commands in a QThread so the window never blocks (section 4)."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot

from emu32.session import Session


class _Worker(QObject):
    finished = Signal(object)  # Outcome, or the exception that ended the command
    stepped = Signal(object)  # Outcome after each step in step delay mode

    def __init__(self, session: Session) -> None:
        super().__init__()
        self.session = session

    @Slot(str, float)
    def execute(self, command: str, delay: float) -> None:
        session = self.session
        try:
            if command == "run" and delay > 0:
                outcome = session.run_with_delay(delay, self.stepped.emit)
            else:
                outcome = {
                    "run": session.run,
                    "step": session.step,
                    "step_over": session.step_over,
                }[command]()
        except Exception as error:  # noqa: BLE001 - the window shows a message, never a traceback
            outcome = error
        self.finished.emit(outcome)


class SessionRunner(QObject):
    """Owns the worker thread. Call start() from the UI thread; results arrive as signals."""

    finished = Signal(object)
    stepped = Signal(object)
    output = Signal(str)
    waiting = Signal(bool)
    _request = Signal(str, float)

    def __init__(self, session: Session, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self.busy = False
        self._thread = QThread()
        self._worker = _Worker(session)
        self._worker.moveToThread(self._thread)
        self._request.connect(self._worker.execute)
        self._worker.finished.connect(self._on_finished)
        self._worker.stepped.connect(self.stepped)
        # Console callbacks run in the worker thread; signals carry them to the UI thread.
        session.console.on_output = self.output.emit
        session.console.on_wait = self.waiting.emit
        self._thread.start()

    def start(self, command: str, delay_ms: int = 0) -> bool:
        """Start "run", "step" or "step_over". Returns False if a command is still running."""
        if self.busy:
            return False
        self.busy = True
        self._request.emit(command, delay_ms / 1000)
        return True

    def stop(self) -> None:
        self.session.stop()

    def shutdown(self) -> None:
        self.session.stop()
        self._thread.quit()
        self._thread.wait()

    @Slot(object)
    def _on_finished(self, outcome: object) -> None:
        self.busy = False
        self.finished.emit(outcome)
