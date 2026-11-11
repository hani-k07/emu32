import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from emu32.gui import settings, theme
from emu32.gui.editor_window import EditorWindow
from emu32.gui.errors import install_excepthook


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("emu32")
    install_excepthook()
    theme.apply(settings.get_str("theme", theme.system_theme()))
    window = EditorWindow()
    window.show()
    files = [arg for arg in sys.argv[1:] if not arg.startswith("-")]

    def start() -> None:
        restored = window.restore_autosave()
        for path in files:
            window.open_file(path)
        if not files and not restored and settings.get_bool("show_welcome", True):
            window.show_welcome()

    # After the event loop starts, so the window is on screen behind any dialog.
    QTimer.singleShot(0, start)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
