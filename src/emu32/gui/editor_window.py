"""Main window: source tabs, compile, error list, files, autosave (sections 8.3 and 8.8)."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QTabWidget,
    QToolButton,
)

from emu32 import __version__
from emu32.assembler import AssemblyError, Program
from emu32.gui import settings, theme
from emu32.gui.code_editor import CodeEditor
from emu32.gui.dialogs import (
    AboutDialog,
    FindReplaceDialog,
    NewFileDialog,
    OptionsDialog,
    WelcomeDialog,
    looks_like_intel,
    read_source,
)
from emu32.gui.help_window import show_help
from emu32.gui.icons import icon
from emu32.gui.tools import show_tool
from emu32.session import Session

FILE_FILTER = "Assembly files (*.asm *.s *.inc);;All files (*)"
AUTOSAVE_SECONDS = 20


def example_files() -> list[Path]:
    folder = resources.files("emu32") / "examples"
    return sorted(Path(str(p)) for p in folder.iterdir() if p.name.endswith(".asm"))


class Document(CodeEditor):
    """One tab: the editor plus where the text lives and which syntax it uses."""

    def __init__(self, path: Path | None, intel: bool, title: str, parent=None) -> None:
        super().__init__(parent)
        self.path = path
        self.intel = intel
        self.title = title

    def display_name(self) -> str:
        return self.path.name if self.path else self.title


class EditorWindow(QMainWindow):
    def __init__(self, session: Session | None = None) -> None:
        super().__init__()
        self.session = session or Session()
        self.session.max_steps = settings.get_int("max_steps", self.session.max_steps)
        self.font_size = settings.get_int("font_size", 11)
        self._untitled = 0
        self.emulator = None
        self.resize(1100, 680)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(lambda i: self.close_tab(self.tabs.widget(i)))
        self.tabs.currentChanged.connect(self._current_changed)
        self.setCentralWidget(self.tabs)

        self.messages = QListWidget()
        self.messages.itemClicked.connect(self._message_clicked)
        self.messages.itemActivated.connect(self._message_clicked)
        dock = QDockWidget("Messages", self)
        dock.setObjectName("messages")
        dock.setWidget(self.messages)
        self.addDockWidget(Qt.BottomDockWidgetArea, dock)
        self.messages_dock = dock
        self.resizeDocks([dock], [110], Qt.Vertical)  # leave most of a small screen to code

        self.find_dialog = FindReplaceDialog(self)
        self.find_dialog.message.connect(lambda text: self.statusBar().showMessage(text, 5000))

        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self.statusBar().showMessage("Ready")

        geometry = settings.settings().value("editor_geometry")
        if isinstance(geometry, QByteArray):
            self.restoreGeometry(geometry)
        state = settings.settings().value("editor_state")
        if isinstance(state, QByteArray):
            self.restoreState(state)

        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start(AUTOSAVE_SECONDS * 1000)
        self._update_title()

    # Building the window

    def _action(self, text, slot, shortcut=None, icon_name=None, enabled=True) -> QAction:
        action = QAction(text, self)
        if icon_name:
            action.setIcon(icon(icon_name))
            action.setProperty("icon_name", icon_name)  # redrawn when the theme changes
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(lambda _=False: slot())
        action.setEnabled(enabled)
        return action

    def _build_actions(self) -> None:
        self.act = {
            "new": self._action("&New...", self.new_file_dialog, "Ctrl+N", "new"),
            "open": self._action("&Open...", self.open_dialog, "Ctrl+O", "open"),
            "save": self._action("&Save", self.save, "Ctrl+S", "save"),
            "save_as": self._action("Save &as...", self.save_as, "Ctrl+Shift+S"),
            "save_listing": self._action("Save &listing...", self.save_listing),
            "close": self._action("&Close tab", lambda: self.close_tab(self.current()), "Ctrl+W"),
            "exit": self._action("E&xit", self.close, "Ctrl+Q"),
            "undo": self._action("&Undo", lambda: self._edit("undo"), "Ctrl+Z"),
            "redo": self._action("&Redo", lambda: self._edit("redo"), "Ctrl+Y"),
            "cut": self._action("Cu&t", lambda: self._edit("cut"), "Ctrl+X"),
            "copy": self._action("&Copy", lambda: self._edit("copy"), "Ctrl+C"),
            "paste": self._action("&Paste", lambda: self._edit("paste"), "Ctrl+V"),
            "select_all": self._action("Select &all", lambda: self._edit("selectAll"), "Ctrl+A"),
            "find": self._action("&Find...", self.show_find, "Ctrl+F"),
            "replace": self._action("R&eplace...", self.show_find, "Ctrl+H"),
            "go_to_line": self._action("&Go to line...", self.go_to_line_dialog, "Ctrl+L"),
            "zoom_in": self._action("Zoom &in", lambda: self.zoom(1), "Ctrl++"),
            "zoom_out": self._action("Zoom &out", lambda: self.zoom(-1), "Ctrl+-"),
            "zoom_reset": self._action("&Normal size", lambda: self.zoom(0), "Ctrl+0"),
            "bookmark": self._action(
                "&Toggle bookmark", lambda: self._doc("toggle_bookmark"), "Ctrl+F2"
            ),
            "next_bookmark": self._action(
                "&Next bookmark", lambda: self._doc("next_bookmark"), "F2"
            ),
            "previous_bookmark": self._action(
                "&Previous bookmark", lambda: self._doc("next_bookmark", True), "Shift+F2"
            ),
            "clear_bookmarks": self._action(
                "&Clear bookmarks", lambda: self._doc("clear_bookmarks")
            ),
            "compile": self._action("&Compile", self.compile, "F5", "compile"),
            "breakpoint": self._action(
                "Toggle &breakpoint", lambda: self._doc("toggle_breakpoint"), "Ctrl+B"
            ),
            "emulate": self._action("&Emulate", self.emulate, "Ctrl+F5", "emulate"),
            "calculator": self._action(
                "&Calculator", lambda: show_tool(self, "calculator"), icon_name="calculator"
            ),
            "converter": self._action(
                "C&onverter", lambda: show_tool(self, "converter"), icon_name="converter"
            ),
            "ascii": self._action("&ASCII table", lambda: show_tool(self, "ascii")),
            "options": self._action("&Options...", self.options_dialog, icon_name="options"),
            "tutorial": self._action("&Quick start tutorial", self.show_quick_start, "F1", "help"),
            "reference": self._action("&Syntax reference", lambda: show_help(self, "syntax")),
            "instructions": self._action(
                "&Instruction reference", lambda: show_help(self, "instructions")
            ),
            "welcome": self._action("&Welcome window", self.show_welcome),
            "about": self._action("&About emu32", self.show_about, icon_name="about"),
        }
        self.act["zoom_in"].setShortcuts([QKeySequence("Ctrl++"), QKeySequence("Ctrl+=")])
        intel = QAction("&Intel/NASM syntax", self)
        intel.setCheckable(True)
        intel.toggled.connect(self._set_intel)
        self.act["intel"] = intel

    def _build_menus(self) -> None:
        bar = self.menuBar()
        a = self.act
        file_menu = bar.addMenu("&File")
        file_menu.addActions([a["new"], a["open"]])
        self.recent_menu = file_menu.addMenu("&Recent files")
        self.examples_menu = file_menu.addMenu("E&xamples")
        file_menu.addSeparator()
        file_menu.addActions([a["save"], a["save_as"], a["save_listing"], a["close"]])
        file_menu.addSeparator()
        file_menu.addAction(a["exit"])
        edit = bar.addMenu("&Edit")
        edit.addActions([a["undo"], a["redo"]])
        edit.addSeparator()
        edit.addActions([a["cut"], a["copy"], a["paste"], a["select_all"]])
        edit.addSeparator()
        edit.addActions([a["find"], a["replace"], a["go_to_line"]])
        edit.addSeparator()
        edit.addActions([a["zoom_in"], a["zoom_out"], a["zoom_reset"]])
        bar.addMenu("&Bookmarks").addActions(
            [a["bookmark"], a["next_bookmark"], a["previous_bookmark"], a["clear_bookmarks"]]
        )
        bar.addMenu("&Assembler").addActions([a["compile"], a["intel"], a["breakpoint"]])
        bar.addMenu("E&mulator").addAction(a["emulate"])
        bar.addMenu("Ma&th").addActions([a["calculator"], a["converter"]])
        bar.addMenu("A&SCII codes").addAction(a["ascii"])
        help_menu = bar.addMenu("&Help")
        help_menu.addActions([a["tutorial"], a["reference"], a["instructions"], a["welcome"]])
        help_menu.addSeparator()
        help_menu.addActions([a["options"], a["about"]])
        self._fill_recent_menu()
        for path in example_files():
            self.examples_menu.addAction(
                self._action(path.stem.replace("_", " "), lambda p=path: self.open_example(p))
            )

    def _build_toolbar(self) -> None:
        bar = self.addToolBar("Main")
        bar.setObjectName("main_toolbar")
        bar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        a = self.act
        bar.addActions([a["new"], a["open"]])
        examples = QToolButton()
        examples.setText("Examples")
        examples.setIcon(icon("examples"))
        examples.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        examples.setMenu(self.examples_menu)
        examples.setPopupMode(QToolButton.InstantPopup)
        bar.addWidget(examples)
        save = QToolButton()
        save.setDefaultAction(a["save"])
        save.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        save_menu = QMenu(save)
        save_menu.addActions([a["save"], a["save_as"], a["save_listing"]])
        save.setMenu(save_menu)
        save.setPopupMode(QToolButton.MenuButtonPopup)
        bar.addWidget(save)
        bar.addSeparator()
        bar.addActions([a["compile"], a["emulate"]])
        bar.addSeparator()
        bar.addActions([a["calculator"], a["converter"], a["options"], a["tutorial"], a["about"]])
        a["tutorial"].setIconText("Help")
        a["about"].setIconText("About")
        a["options"].setIconText("Options")

    # Documents

    def current(self) -> Document | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, Document) else None

    def documents(self) -> list[Document]:
        return [self.tabs.widget(i) for i in range(self.tabs.count())]

    def _doc(self, method: str, *args) -> None:
        doc = self.current()
        if doc is not None:
            getattr(doc, method)(*args)

    def _edit(self, method: str) -> None:
        self._doc(method)

    def add_document(
        self, text: str, path: Path | None = None, intel: bool = False, title: str | None = None
    ) -> Document:
        if title is None:
            self._untitled += 1
            title = f"untitled{self._untitled}.asm"
        doc = Document(path, intel, title)
        doc.setPlainText(text)
        doc.document().setModified(False)
        doc.zoom(self.font_size - doc.font().pointSize())
        doc.document().modificationChanged.connect(lambda _m, d=doc: self._update_tab(d))
        index = self.tabs.addTab(doc, doc.display_name())
        self.tabs.setCurrentIndex(index)
        self._update_tab(doc)
        doc.setFocus()
        return doc

    def new_file_dialog(self) -> None:
        dialog = NewFileDialog(self)
        if dialog.exec():
            self.add_document(dialog.source(), intel=dialog.intel.isChecked())

    def open_dialog(self) -> None:
        start = str(self.current().path.parent) if self.current() and self.current().path else ""
        path, _ = QFileDialog.getOpenFileName(self, "Open", start, FILE_FILTER)
        if path:
            self.open_file(path)

    def open_file(self, path: str | Path) -> Document | None:
        path = Path(path).resolve()
        for doc in self.documents():
            if doc.path == path:
                self.tabs.setCurrentWidget(doc)
                return doc
        try:
            text, fell_back = read_source(path)
        except OSError as error:
            QMessageBox.warning(self, "emu32", f"Cannot open {path}:\n{error.strerror}")
            return None
        doc = self.add_document(text, path, looks_like_intel(text))
        if fell_back:
            self.statusBar().showMessage(
                f"{path.name} was not UTF-8; it was read as Windows-1252 and will be saved as UTF-8"
            )
        self._remember(path)
        return doc

    def open_example(self, path: Path) -> Document:
        text = path.read_text(encoding="utf-8")
        return self.add_document(text, intel=looks_like_intel(text), title=path.name)

    def save(self, doc: Document | None = None) -> bool:
        doc = doc or self.current()
        if doc is None:
            return False
        if doc.path is None:
            return self.save_as(doc)
        return self._write(doc, doc.path)

    def save_as(self, doc: Document | None = None) -> bool:
        doc = doc or self.current()
        if doc is None:
            return False
        start = str(doc.path or Path.home() / doc.display_name())
        path, _ = QFileDialog.getSaveFileName(self, "Save as", start, FILE_FILTER)
        if not path:
            return False
        return self._write(doc, Path(path))

    def _write(self, doc: Document, path: Path) -> bool:
        try:
            path.write_text(doc.toPlainText(), encoding="utf-8")
        except OSError as error:
            QMessageBox.warning(self, "emu32", f"Cannot save {path}:\n{error.strerror}")
            return False
        doc.path = path.resolve()
        doc.document().setModified(False)
        self._update_tab(doc)
        self._remember(doc.path)
        self.statusBar().showMessage(f"Saved {doc.path}", 5000)
        return True

    def save_listing(self) -> None:
        doc = self.current()
        program = self.compile()
        if doc is None or program is None:
            return
        start = str((doc.path or Path.home() / doc.display_name()).with_suffix(".lst"))
        path, _ = QFileDialog.getSaveFileName(self, "Save listing", start, "Listing (*.lst)")
        if path:
            Path(path).write_text(program.listing(doc.toPlainText()), encoding="utf-8")
            self.statusBar().showMessage(f"Listing saved to {path}", 5000)

    def close_tab(self, doc: Document | None) -> bool:
        if doc is None or not self.maybe_save(doc):
            return False
        self.tabs.removeTab(self.tabs.indexOf(doc))
        doc.deleteLater()
        return True

    def maybe_save(self, doc: Document) -> bool:
        """Ask before losing changes. Returns False if the user cancels."""
        if not doc.document().isModified():
            return True
        self.tabs.setCurrentWidget(doc)
        answer = self.ask_unsaved(doc)
        if answer == QMessageBox.Save:
            return self.save(doc)
        return answer == QMessageBox.Discard

    def ask_unsaved(self, doc: Document) -> QMessageBox.StandardButton:
        return QMessageBox.question(
            self,
            "Unsaved changes",
            f"Save the changes to {doc.display_name()}?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )

    def _remember(self, path: Path) -> None:
        settings.add_recent_file(str(path))
        self._fill_recent_menu()

    def _fill_recent_menu(self) -> None:
        self.recent_menu.clear()
        files = settings.recent_files()
        for number, name in enumerate(files, start=1):
            self.recent_menu.addAction(
                self._action(f"&{number % 10} {name}", lambda n=name: self.open_file(n))
            )
        self.recent_menu.setEnabled(bool(files))

    def _update_tab(self, doc: Document) -> None:
        index = self.tabs.indexOf(doc)
        if index >= 0:
            star = "*" if doc.document().isModified() else ""
            self.tabs.setTabText(index, doc.display_name() + star)
            self.tabs.setTabToolTip(index, str(doc.path or doc.display_name()))
        self._update_title()

    def _current_changed(self, _index: int) -> None:
        doc = self.current()
        self.act["intel"].blockSignals(True)
        self.act["intel"].setChecked(bool(doc and doc.intel))
        self.act["intel"].blockSignals(False)
        self.find_dialog.editor = doc
        self._update_title()

    def _update_title(self) -> None:
        doc = self.current()
        self.setWindowTitle(f"{doc.display_name()} - emu32" if doc else f"emu32 {__version__}")

    def _set_intel(self, value: bool) -> None:
        if self.current():
            self.current().intel = value

    # Compile and emulate

    def compile(self) -> Program | None:
        doc = self.current()
        if doc is None:
            return None
        self.messages.clear()
        try:
            program = self.session.compile(doc.toPlainText(), doc.intel)
        except AssemblyError as error:
            for message in error.errors:
                item = QListWidgetItem(str(message))
                item.setData(Qt.UserRole, message.line)
                self.messages.addItem(item)
            doc.set_error_lines({m.line for m in error.errors})
            count = len(error.errors)
            self.statusBar().showMessage(f"{count} error{'s' if count != 1 else ''}")
            self.messages_dock.show()
            if error.errors:
                doc.go_to_line(error.errors[0].line)
            return None
        doc.set_error_lines(set())
        summary = (
            f"Compiled {doc.display_name()}: {len(program.code)} bytes of code, "
            f"{len(program.data)} bytes of data, {program.instruction_count} instructions"
        )
        self.messages.addItem(summary)
        for warning in program.warnings:
            item = QListWidgetItem(f"warning: {warning}")
            item.setData(Qt.UserRole, warning.line)
            self.messages.addItem(item)
        self.statusBar().showMessage(summary)
        return program

    def _message_clicked(self, item: QListWidgetItem) -> None:
        line = item.data(Qt.UserRole)
        if line and self.current():
            self.current().go_to_line(int(line))

    def emulate(self) -> None:
        if self.compile() is not None:
            self.open_emulator(self.current())

    def open_emulator(self, doc: Document) -> None:
        """Load the tab's program into the emulator window, with the tab's breakpoints.
        Reload in the emulator window takes the tab's current text."""
        if self.emulator is None:
            from emu32.gui.emulator_window import EmulatorWindow

            self.emulator = EmulatorWindow()
        self.emulator.file_path = None
        self.emulator.source_provider = lambda d=doc: d.toPlainText()
        loaded = self.emulator.load_source(
            doc.toPlainText(), doc.intel, doc.breakpoint_lines(), doc.display_name()
        )
        if loaded:
            self.emulator.show()
            self.emulator.raise_()
            self.emulator.activateWindow()

    # Other commands

    def show_find(self) -> None:
        self.find_dialog.editor = self.current()
        selected = self.current().textCursor().selectedText() if self.current() else ""
        if selected:
            self.find_dialog.find_text.setText(selected)
        self.find_dialog.show()
        self.find_dialog.raise_()
        self.find_dialog.find_text.setFocus()

    def go_to_line_dialog(self) -> None:
        doc = self.current()
        if doc is None:
            return
        line, ok = QInputDialog.getInt(
            self, "Go to line", "Line:", doc.current_line(), 1, doc.blockCount()
        )
        if ok:
            doc.go_to_line(line)

    def zoom(self, steps: int) -> None:
        self.font_size = 11 if steps == 0 else min(48, max(6, self.font_size + steps))
        for doc in self.documents():
            doc.zoom(self.font_size - doc.font().pointSize())
        settings.put("font_size", self.font_size)

    def options_dialog(self) -> None:
        dialog = OptionsDialog(
            settings.get_str("theme", theme.system_theme()),
            self.font_size,
            settings.get_bool("show_welcome", True),
            self.session.max_steps,
            self,
        )
        if not dialog.exec():
            return
        name = dialog.theme.currentData()
        settings.put("theme", name)
        settings.put("show_welcome", dialog.show_welcome.isChecked())
        settings.put("max_steps", dialog.max_steps.value())
        self.session.max_steps = dialog.max_steps.value()
        self.switch_theme(name)
        self.zoom(dialog.font_size.value() - self.font_size)

    def switch_theme(self, name: str) -> None:
        """Change the theme while the window is open; colors drawn in code follow too."""
        theme.apply(name)
        for doc in self.documents():
            doc.refresh_theme()
        for action in self.act.values():
            if action.property("icon_name"):
                action.setIcon(icon(action.property("icon_name")))
        if self.emulator is not None:
            self.emulator.source.refresh_theme()
            self.emulator.refresh()

    def show_welcome(self) -> None:
        dialog = WelcomeDialog(
            settings.recent_files(), settings.get_bool("show_welcome", True), self
        )
        dialog.exec()
        settings.put("show_welcome", dialog.show_at_start.isChecked())
        self.handle_welcome_choice(dialog.choice)

    def handle_welcome_choice(self, choice: str | None) -> None:
        if choice == "new":
            self.new_file_dialog()
        elif choice == "examples":
            names = [p.name for p in example_files()]
            name, ok = QInputDialog.getItem(self, "Code examples", "Example:", names, 0, False)
            if ok:
                self.open_example(next(p for p in example_files() if p.name == name))
        elif choice == "tutorial":
            self.show_quick_start()
        elif choice:
            self.open_file(choice)

    def show_quick_start(self) -> None:
        show_help(self, "quickstart")

    def show_about(self) -> None:
        AboutDialog(self).exec()

    # Autosave and closing

    @staticmethod
    def autosave_dir() -> Path:
        return settings.app_data_dir() / "autosave"

    def autosave(self) -> None:
        """Keep a copy of every changed tab, so work survives a crash or forced close."""
        folder = self.autosave_dir()
        folder.mkdir(exist_ok=True)
        entries = []
        for number, doc in enumerate(self.documents()):
            if not doc.document().isModified():
                continue
            name = f"{number}.asm"
            (folder / name).write_text(doc.toPlainText(), encoding="utf-8")
            entries.append(
                {
                    "file": name,
                    "path": str(doc.path or ""),
                    "title": doc.display_name(),
                    "intel": doc.intel,
                }
            )
        for old in folder.glob("*.asm"):
            if old.name not in {e["file"] for e in entries}:
                old.unlink()
        (folder / "index.json").write_text(json.dumps(entries), encoding="utf-8")

    def clear_autosave(self) -> None:
        folder = self.autosave_dir()
        for item in folder.glob("*"):
            item.unlink()

    def restore_autosave(self) -> int:
        """Offer to reopen tabs saved by autosave. Returns how many were restored."""
        index = self.autosave_dir() / "index.json"
        try:
            entries = json.loads(index.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return 0
        if not entries or not self.ask_restore(len(entries)):
            self.clear_autosave()
            return 0
        for entry in entries:
            text = (self.autosave_dir() / entry["file"]).read_text(encoding="utf-8")
            path = Path(entry["path"]) if entry["path"] else None
            doc = self.add_document(text, path, entry["intel"], title=entry["title"])
            doc.document().setModified(True)
        self.clear_autosave()
        self.autosave()
        return len(entries)

    def ask_restore(self, count: int) -> bool:
        answer = QMessageBox.question(
            self,
            "Restore work",
            f"emu32 did not close normally. Restore {count} unsaved file(s)?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        return answer == QMessageBox.Yes

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        for doc in self.documents():
            if not self.maybe_save(doc):
                event.ignore()
                return
        self.autosave_timer.stop()
        self.clear_autosave()
        if self.emulator is not None:
            self.emulator.close()
            self.emulator.shutdown()
        settings.put("editor_geometry", self.saveGeometry())
        settings.put("editor_state", self.saveState())
        event.accept()
