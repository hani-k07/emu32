"""Emulator window (section 8.4): controls, registers, memory, disassembly and tool panels.

Commands run in the worker thread. While one runs, the window reads only the snapshot the
session publishes between chunks; when the engine is idle (finished, or pausing between
steps in step delay mode) it reads the full state under the session lock.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from emu32.assembler import AssemblyError
from emu32.emulator import StopReason
from emu32.gui import theme
from emu32.gui.cpu_view import CpuStructureWindow
from emu32.gui.dialogs import AboutDialog, looks_like_intel, read_source
from emu32.gui.errors import report_exception
from emu32.gui.models import DisassemblyModel, MemoryModel
from emu32.gui.panels import (
    AuxPanel,
    DebugPanel,
    FlagsPanel,
    RegistersPanel,
    ScreenPanel,
    SourcePanel,
    StackPanel,
    VarsPanel,
    fixed_font,
)
from emu32.gui.worker import SessionRunner
from emu32.session import Outcome, Session, SessionError

REFRESH_MS = 33  # at most about 30 refreshes per second (section 4)
FILE_FILTER = "Assembly files (*.asm *.s *.inc);;All files (*)"
PROJECTOR_SCALE = 1.6


def scale_fonts(root: QWidget, factor: float) -> None:
    """Scale every widget's font relative to the size it had the first time."""
    for widget in [root, *root.findChildren(QWidget)]:
        base = widget.property("base_point_size")
        if base is None:
            base = widget.font().pointSizeF()
            widget.setProperty("base_point_size", base)
        font = widget.font()
        font.setPointSizeF(max(6.0, float(base) * factor))
        widget.setFont(font)


class EmulatorWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.Window)
        self.setWindowTitle("emu32 emulator")
        self.resize(1200, 720)
        self.session = Session()
        self.runner = SessionRunner(self.session, self)
        self.mode = self.session.mode
        self.source_provider: Callable[[], str] | None = None
        self.file_path: Path | None = None
        self.title = ""
        self.before_registers: dict[str, int] = {}
        self.before_flags: dict[str, int] = {}
        self.dirty = False
        self.font_scale = 1.0
        self.projector = False

        self._build_panels()
        self._build_actions()
        self._build_menus()
        self._build_controls()
        self._build_docks()
        self._connect()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._live_refresh)
        self._set_busy(False)
        self.statusBar().showMessage("Load a program, or press Emulate in the editor")

    # Building

    def _build_panels(self) -> None:
        fmt = self.mode.format_address
        self.registers = RegistersPanel(self.mode)
        self.memory_model = MemoryModel(fmt)
        self.memory_view = QTableView()
        self.memory_view.setModel(self.memory_model)
        self.memory_view.setFont(fixed_font())
        self.memory_view.verticalHeader().setVisible(False)
        self.memory_view.verticalHeader().setDefaultSectionSize(self.fontMetrics().height() + 4)
        self.memory_view.setSelectionBehavior(QTableView.SelectRows)
        # Fixed widths: sizing to contents would measure all 65,536 rows.
        char = self.memory_view.fontMetrics().horizontalAdvance("W")
        for column, chars in enumerate((2, 10, 4, 5, 7)):
            self.memory_view.setColumnWidth(column, char * chars + 12)
        self.memory_view.horizontalHeader().setStretchLastSection(True)
        self.address_box = QLineEdit(fmt(self.mode.region("data").start))
        self.address_box.setToolTip("Address in hex. Press Enter to show it.")
        self.disassembly_model = DisassemblyModel(fmt)
        self.disassembly_view = QTableView()
        self.disassembly_view.setModel(self.disassembly_model)
        self.disassembly_view.setFont(fixed_font())
        self.disassembly_view.verticalHeader().setVisible(False)
        self.disassembly_view.verticalHeader().setDefaultSectionSize(
            self.fontMetrics().height() + 4
        )
        self.disassembly_view.setSelectionBehavior(QTableView.SelectRows)
        header = self.disassembly_view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.disassembly_view.setToolTip("Double-click an instruction to toggle a breakpoint.")
        self.screen = ScreenPanel()
        self.source = SourcePanel()
        self.aux = AuxPanel()
        self.vars = VarsPanel()
        self.debug = DebugPanel()
        self.stack = StackPanel(self.mode)
        self.flags = FlagsPanel()
        self.cpu = CpuStructureWindow(self)
        self.cpu.setWindowFlag(Qt.Window)

        memory = QWidget()
        column = QVBoxLayout(memory)
        column.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(QLabel("&Address:", buddy=self.address_box))
        row.addWidget(self.address_box)
        column.addLayout(row)
        column.addWidget(self.memory_view)
        splitter = QSplitter()
        for title, widget in (
            ("Registers", self.registers),
            ("Memory", memory),
            ("Disassembly", self.disassembly_view),
        ):
            box = QWidget()
            layout = QVBoxLayout(box)
            layout.setContentsMargins(4, 4, 4, 4)
            layout.addWidget(QLabel(f"<b>{title}</b>"))
            layout.addWidget(widget)
            splitter.addWidget(box)
        splitter.setSizes([360, 330, 510])
        self.splitter = splitter

    def _action(self, text, slot, shortcut=None, enabled=True) -> QAction:
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(lambda _=False: slot())
        action.setEnabled(enabled)
        return action

    def _build_actions(self) -> None:
        self.act = {
            "load": self._action("&Load...", self.load_dialog, "Ctrl+O"),
            "reload": self._action("&Reload", self.reload, "Ctrl+R"),
            "reset": self._action("Rese&t", self.reset, "Ctrl+Shift+R"),
            "close": self._action("&Close", self.close, "Ctrl+W"),
            "step": self._action("&Single step", lambda: self.command("step"), "F8"),
            "step_over": self._action("Step &over", lambda: self.command("step_over"), "F10"),
            "step_back": self._action("Step &back", self.step_back, "Shift+F8"),
            "run": self._action("&Run", lambda: self.command("run"), "F9"),
            "stop": self._action("S&top", self.stop, "Esc"),
            "breakpoint": self._action("Toggle &breakpoint", self.toggle_breakpoint_here, "Ctrl+B"),
            "go_to": self._action("&Go to address...", self.focus_address, "Ctrl+G"),
            "cpu": self._action("&CPU structure", self.show_cpu, "Ctrl+Shift+C"),
            "zoom_in": self._action("Zoom &in", lambda: self.zoom(0.1), "Ctrl++"),
            "zoom_out": self._action("Zoom &out", lambda: self.zoom(-0.1), "Ctrl+-"),
            "about": self._action("&About emu32", lambda: AboutDialog(self).exec()),
            "calculator": self._action("&Calculator", lambda: None, enabled=False),
            "converter": self._action("C&onverter", lambda: None, enabled=False),
        }
        self.act["zoom_in"].setShortcuts([QKeySequence("Ctrl++"), QKeySequence("Ctrl+=")])
        upper = QAction("&Uppercase mnemonics", self)
        upper.setCheckable(True)
        upper.toggled.connect(self._set_uppercase)
        self.act["uppercase"] = upper
        projector = QAction("&Projector mode", self)
        projector.setCheckable(True)
        projector.setShortcut(QKeySequence("Ctrl+Shift+P"))
        projector.toggled.connect(self.set_projector)
        self.act["projector"] = projector

    def _build_menus(self) -> None:
        a, bar = self.act, self.menuBar()
        file_menu = bar.addMenu("&File")
        file_menu.addActions([a["load"], a["reload"], a["reset"]])
        file_menu.addSeparator()
        file_menu.addAction(a["close"])
        bar.addMenu("Ma&th").addActions([a["calculator"], a["converter"]])
        bar.addMenu("&Debug").addActions(
            [a["step"], a["step_over"], a["step_back"], a["run"], a["stop"], a["breakpoint"],
             a["go_to"]]
        )  # fmt: skip
        self.view_menu = bar.addMenu("&View")
        for title in ("E&xternal", "Virtual &devices", "Virtual d&rive"):
            reserved = bar.addMenu(title)
            reserved.setEnabled(False)
        bar.addMenu("&Help").addAction(a["about"])

    def _build_controls(self) -> None:
        top = QToolBar("Controls")
        top.setObjectName("controls")
        self.buttons: dict[str, QPushButton] = {}
        for key, label in (
            ("load", "Load"),
            ("reload", "Reload"),
            ("step_back", "Step back"),
            ("step", "Single step"),
            ("run", "Run"),
            ("stop", "Stop"),
        ):
            button = QPushButton(label)
            button.clicked.connect(self.act[key].trigger)
            button.setToolTip(f"{label} ({self.act[key].shortcut().toString()})")
            top.addWidget(button)
            self.buttons[key] = button
        top.addSeparator()
        self.delay = QSlider(Qt.Horizontal)
        self.delay.setRange(0, 1000)
        self.delay.setSingleStep(10)
        self.delay.setPageStep(100)
        self.delay.setFixedWidth(180)
        self.delay_label = QLabel("Step delay: 0 ms")
        self.delay.valueChanged.connect(lambda v: self.delay_label.setText(f"Step delay: {v} ms"))
        top.addWidget(self.delay_label)
        top.addWidget(self.delay)
        self.addToolBar(Qt.TopToolBarArea, top)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.splitter, 1)
        row = QHBoxLayout()
        self.bottom_buttons: dict[str, QPushButton] = {}
        for name in ("Screen", "Source", "Reset", "Aux", "Vars", "Debug", "Stack", "Flags", "CPU"):
            button = QPushButton(name)
            row.addWidget(button)
            self.bottom_buttons[name] = button
        layout.addLayout(row)
        self.setCentralWidget(central)

    def _build_docks(self) -> None:
        self.docks: dict[str, QDockWidget] = {}
        placement = {
            "Screen": (self.screen, Qt.BottomDockWidgetArea, True),
            "Source": (self.source, Qt.RightDockWidgetArea, True),
            "Aux": (self.aux, Qt.RightDockWidgetArea, False),
            "Vars": (self.vars, Qt.RightDockWidgetArea, False),
            "Debug": (self.debug, Qt.RightDockWidgetArea, False),
            "Stack": (self.stack, Qt.RightDockWidgetArea, False),
            "Flags": (self.flags, Qt.RightDockWidgetArea, False),
        }
        for name, (widget, area, visible) in placement.items():
            dock = QDockWidget(name, self)
            dock.setObjectName(name.lower())
            dock.setWidget(widget)
            self.addDockWidget(area, dock)
            dock.setVisible(visible)
            self.docks[name] = dock
            action = dock.toggleViewAction()
            action.setText(f"&{name}")
            self.view_menu.addAction(action)
            self.bottom_buttons[name].clicked.connect(lambda _=False, d=dock: self._toggle_dock(d))
        for name in ("Aux", "Vars", "Debug", "Stack", "Flags"):
            self.tabifyDockWidget(self.docks["Source"], self.docks[name])
        self.docks["Source"].raise_()
        # Keep the main three columns large on a 1366x768 screen.
        self.resizeDocks([self.docks["Screen"]], [150], Qt.Vertical)
        self.resizeDocks([self.docks["Source"]], [360], Qt.Horizontal)
        self.view_menu.addSeparator()
        self.view_menu.addActions(
            [self.act["cpu"], self.act["uppercase"], self.act["projector"], self.act["zoom_in"],
             self.act["zoom_out"]]
        )  # fmt: skip
        self.bottom_buttons["Reset"].clicked.connect(self.reset)
        self.bottom_buttons["CPU"].clicked.connect(self.show_cpu)

    def _connect(self) -> None:
        self.runner.finished.connect(self._finished)
        self.runner.stepped.connect(lambda _outcome: setattr(self, "dirty", True))
        self.runner.output.connect(self.screen.append)
        self.runner.waiting.connect(self._waiting)
        self.screen.submitted.connect(lambda text: self.session.console.feed(text + "\n"))
        self.registers.edit_requested.connect(self.edit_register)
        self.address_box.returnPressed.connect(self.show_address)
        self.disassembly_view.doubleClicked.connect(self._disassembly_double_clicked)
        self.source.breakpoints_changed.connect(self._source_breakpoints_changed)
        self.debug.remove_breakpoint.connect(self._toggle_line)
        self.debug.watches_changed.connect(self.refresh)

    def _toggle_dock(self, dock: QDockWidget) -> None:
        dock.setVisible(not dock.isVisible() or dock.visibleRegion().isEmpty())
        if dock.isVisible():
            dock.raise_()

    # Loading

    def load_source(
        self, source: str, intel: bool = False, breakpoints=(), title: str = ""
    ) -> bool:
        """Assemble and load. Returns False (after showing the errors) if it does not
        assemble."""
        if self.runner.busy:
            return False
        for line in self.session.breakpoint_lines:
            self.session.toggle_breakpoint(line)
        try:
            self.session.load(source, intel)
        except AssemblyError as error:
            self._show_assembly_errors(error)
            return False
        for line in breakpoints:
            if line not in self.session.breakpoint_lines:
                self.session.toggle_breakpoint(line)
        self.title = title or "program"
        self.setWindowTitle(f"{self.title} - emu32 emulator")
        self.source.set_source(source, self.session.breakpoint_lines)
        self.screen.set_text("")
        self.vars.reset()
        self._after_load()
        return True

    def _after_load(self) -> None:
        self.before_registers, self.before_flags = {}, {}
        self.memory_model.show(0, [])
        self.refresh()
        self.statusBar().showMessage(f"Loaded {self.title}")

    def _show_assembly_errors(self, error: AssemblyError) -> None:
        shown = "\n".join(str(e) for e in error.errors[:12])
        more = len(error.errors) - 12
        if more > 0:
            shown += f"\n... and {more} more"
        QMessageBox.warning(self, "The program does not assemble", shown)

    def load_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load", "", FILE_FILTER)
        if path:
            self.load_file(path)

    def load_file(self, path: str | Path) -> bool:
        text, _ = read_source(path)
        self.file_path = Path(path)
        self.source_provider = None
        return self.load_source(text, looks_like_intel(text), title=self.file_path.name)

    def reload(self) -> None:
        if self.runner.busy:
            return
        if self.source_provider is not None:
            source = self.source_provider()
        elif self.file_path is not None:
            source = read_source(self.file_path)[0]
        else:
            source = self.session.source
        if source is None:
            return
        try:
            self.session.reload(source)
        except AssemblyError as error:
            self._show_assembly_errors(error)
            return
        self.source.set_source(source, self.session.breakpoint_lines)
        self.screen.set_text("")
        self.vars.reset()
        self._after_load()

    def reset(self) -> None:
        if self.runner.busy or self.session.program is None:
            return
        self.session.reset()
        self.screen.set_text("")
        self.vars.reset()
        self._after_load()
        self.statusBar().showMessage("Reset to the start of the program")

    # Commands

    def command(self, name: str) -> None:
        if self.runner.busy or self.session.program is None:
            return
        with self.session.lock:
            self.before_registers = self.session.emulator.registers()
            self.before_flags = self.session.emulator.flags()
        delay = self.delay.value() if name == "run" else 0
        if self.runner.start(name, delay):
            self._set_busy(True)

    def step_back(self) -> None:
        if self.runner.busy or self.session.program is None:
            return
        with self.session.lock:
            self.before_registers = self.session.emulator.registers()
            self.before_flags = self.session.emulator.flags()
        if self.session.step_back():
            self.statusBar().showMessage(f"Stepped back to line {self.session.current_line()}")
        else:
            self.statusBar().showMessage("Nothing to step back (Run clears the history)")
        self.refresh()

    def stop(self) -> None:
        self.runner.stop()

    def _set_busy(self, busy: bool) -> None:
        loaded = self.session.program is not None
        for key in ("load", "reload", "reset", "step", "step_over", "step_back", "run"):
            self.act[key].setEnabled(not busy and (loaded or key == "load"))
        self.act["load"].setEnabled(not busy)
        self.act["stop"].setEnabled(busy)
        for key, button in self.buttons.items():
            button.setEnabled(self.act[key].isEnabled())
        self.bottom_buttons["Reset"].setEnabled(self.act["reset"].isEnabled())
        if busy:
            self.refresh_timer.start(REFRESH_MS)
            self.statusBar().showMessage("Running...")
        else:
            self.refresh_timer.stop()

    def _finished(self, outcome: object) -> None:
        self._set_busy(False)
        self.screen.set_waiting(False)
        if isinstance(outcome, SessionError):
            self.statusBar().showMessage(str(outcome))
            return
        if isinstance(outcome, Exception):
            report_exception(self, outcome)
            return
        self.refresh(outcome)
        if outcome.reason is StopReason.ERROR:
            QMessageBox.warning(self, "Run-time error", outcome.message)

    def _waiting(self, waiting: bool) -> None:
        self.screen.set_waiting(waiting)
        if waiting:
            self.docks["Screen"].show()
            self.docks["Screen"].raise_()
            self.statusBar().showMessage("Waiting for input in the Screen window")

    # Refreshing

    def _live_refresh(self) -> None:
        """Timer tick while a command runs."""
        if self.session.lock.acquire(blocking=False):
            try:
                if self.dirty:  # step delay mode, between two steps
                    self.dirty = False
                    self._refresh_locked(None, live=True)
            finally:
                self.session.lock.release()
            return
        registers, steps = self.session.live
        self.registers.refresh(registers, self.before_registers)
        self.aux.counter.setText(f"Instructions executed: {steps:,}")
        self.statusBar().showMessage(f"Running... {steps:,} instructions")

    def refresh(self, outcome: Outcome | None = None) -> None:
        if self.session.program is None:
            return
        with self.session.lock:
            self._refresh_locked(outcome)

    def _refresh_locked(self, outcome: Outcome | None, live: bool = False) -> None:
        session, emu = self.session, self.session.emulator
        registers, flags = emu.registers(), emu.flags()
        eip = registers[self.mode.instruction_pointer]
        self.registers.refresh(registers, self.before_registers)
        self.flags.refresh(flags, self.before_flags)
        self.stack.refresh(registers, session.read_bytes)
        self.vars.refresh(session.variables(), self.mode.format_address)
        session.watches = self.debug.watches
        self.debug.refresh(session.breakpoint_lines, session.watch_values())
        self.aux.refresh(emu.total_steps, session.trace, self.mode.format_address)
        self.screen.set_text(session.console.output())
        start = (
            self.memory_model.start
            if self.memory_model.values
            else self._window_for(self.mode.region("data").start)
        )
        self.memory_model.show(start, session.read_bytes(start, MemoryModel.WINDOW))
        self.disassembly_model.show(session.listing(), eip, frozenset(emu.breakpoints))
        row = self.disassembly_model.row_of(eip)
        if row is not None:
            self.disassembly_view.scrollTo(self.disassembly_model.index(row, 0))
        line = session.current_line()
        self.source.show_line(line)
        last = session.trace[-1] if session.trace else None
        self.cpu.show_record(last if last is not None and last.address != eip else None)
        if not live:
            where = f"line {line}" if line else self.mode.format_address(eip)
            text = outcome.message if outcome and outcome.message else f"at {where}"
            if emu.exited and not (outcome and outcome.message):
                text = "the program has ended"
            self.statusBar().showMessage(f"{text}    instructions: {emu.total_steps:,}")

    # Memory, registers, breakpoints

    def _window_for(self, address: int) -> int:
        return address & ~(MemoryModel.WINDOW - 1)

    def focus_address(self) -> None:
        self.address_box.setFocus()
        self.address_box.selectAll()

    def show_address(self) -> None:
        try:
            address = int(self.address_box.text().strip().rstrip("hH"), 16)
        except ValueError:
            self.statusBar().showMessage("Type the address in hex, for example 00500000")
            return
        start = self._window_for(address)
        if self.session.program is not None and not self.runner.busy:
            with self.session.lock:
                self.memory_model.show(start, self.session.read_bytes(start, MemoryModel.WINDOW))
        self.memory_view.scrollTo(
            self.memory_model.index(address - start, 1), QTableView.PositionAtTop
        )
        self.memory_view.selectRow(address - start)

    def edit_register(self, name: str) -> None:
        if self.runner.busy or self.session.program is None:
            return
        current = self.session.emulator.registers()[name]
        text, ok = QInputDialog.getText(
            self, "Change register", f"New value for {name} (hex):", text=f"{current:08X}"
        )
        if not ok:
            return
        try:
            value = int(text.strip().rstrip("hH"), 16)
        except ValueError:
            self.statusBar().showMessage(f"'{text}' is not a hex number")
            return
        self.before_registers = self.session.emulator.registers()
        self.session.set_register(name, value)
        self.refresh()

    def _toggle_line(self, line: int) -> None:
        self.session.toggle_breakpoint(line)
        self.source.sync_breakpoints(self.session.breakpoint_lines)
        self.refresh()

    def toggle_breakpoint_here(self) -> None:
        line = self.source.current_line() if self.source.hasFocus() else self.session.current_line()
        if line:
            self._toggle_line(line)

    def _disassembly_double_clicked(self, index: QModelIndex) -> None:
        line = self.disassembly_model.rows[index.row()][3]
        if line:
            self._toggle_line(line)

    def _source_breakpoints_changed(self) -> None:
        wanted = set(self.source.breakpoint_lines())
        for line in wanted ^ set(self.session.breakpoint_lines):
            self.session.toggle_breakpoint(line)
        self.source.sync_breakpoints(self.session.breakpoint_lines)
        self.refresh()

    # View

    def _set_uppercase(self, on: bool) -> None:
        self.disassembly_model.uppercase = on
        self.disassembly_view.viewport().update()

    def show_cpu(self) -> None:
        self.cpu.show()
        self.cpu.raise_()

    def zoom(self, step: float) -> None:
        self.font_scale = min(3.0, max(0.6, self.font_scale + step))
        self._apply_scale()

    def _apply_scale(self) -> None:
        factor = self.font_scale * (PROJECTOR_SCALE if self.projector else 1.0)
        scale_fonts(self, factor)
        scale_fonts(self.cpu, factor)

    def set_projector(self, on: bool) -> None:
        """Large fonts and high contrast for showing the program to a class."""
        self.projector = on
        if on:
            self._theme_before = theme.current_name()
            theme.apply("contrast")
        else:
            theme.apply(getattr(self, "_theme_before", "light"))
        self.source.refresh_theme()
        self._apply_scale()
        self.refresh()

    # Closing

    def shutdown(self) -> None:
        self.runner.shutdown()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        self.runner.stop()
        self.cpu.close()
        event.accept()
