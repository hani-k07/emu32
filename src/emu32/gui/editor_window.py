from PySide6.QtWidgets import QMainWindow

from emu32 import __version__


class EditorWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"emu32 {__version__}")
        self.resize(1000, 700)
