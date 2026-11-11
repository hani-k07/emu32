import sys

from PySide6.QtWidgets import QApplication

from emu32.gui.editor_window import EditorWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("emu32")
    window = EditorWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
