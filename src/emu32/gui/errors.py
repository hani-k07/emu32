"""Unexpected errors: a short message with Copy details, and the full text in a log file.

Students never see a raw Python traceback (section 8.8).
"""

from __future__ import annotations

import datetime
import sys
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from emu32 import __version__
from emu32.gui.settings import app_data_dir


def log_path():
    return app_data_dir() / "emu32.log"


def write_log(details: str) -> None:
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    try:
        with log_path().open("a", encoding="utf-8") as log:
            log.write(f"--- {stamp} emu32 {__version__}\n{details}\n")
    except OSError:
        pass  # a failing log must not cause a second error


def show_error(parent: QWidget | None, message: str, details: str = "") -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle("emu32")
    box.setText(message)
    if details:
        box.setInformativeText(f"Details were saved to {log_path()}")
        copy = box.addButton("Copy details", QMessageBox.ActionRole)
        copy.clicked.disconnect()
        copy.clicked.connect(lambda: QApplication.clipboard().setText(details))
    box.addButton(QMessageBox.Ok)
    box.exec()


def report_exception(parent: QWidget | None, error: BaseException) -> None:
    details = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    write_log(details)
    show_error(parent, "Something went wrong inside emu32. Your files are not affected.", details)


def install_excepthook() -> None:
    def hook(kind, error, tb):
        if issubclass(kind, KeyboardInterrupt):
            sys.__excepthook__(kind, error, tb)
            return
        report_exception(QApplication.activeWindow(), error.with_traceback(tb))

    sys.excepthook = hook
