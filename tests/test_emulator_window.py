import time

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QInputDialog, QMessageBox

from emu32.gui import theme
from emu32.gui.editor_window import EditorWindow
from emu32.gui.emulator_window import EmulatorWindow
from emu32.gui.models import MemoryModel

LOOP = """INCLUDE Irvine32.inc
.data
total DWORD 0
.code
main PROC
    mov  ecx, 3
top:
    add  total, ecx
    loop top
    mov  eax, total
    call WriteDec
    exit
main ENDP
END main
"""
ADD_LINE, LOOP_LINE = 8, 9


@pytest.fixture
def window(qtbot, monkeypatch):
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: messages.append(a[2]))
    win = EmulatorWindow()
    win.messages = messages
    qtbot.addWidget(win)
    win.show()
    yield win
    win.shutdown()


def finish(qtbot, win, timeout=10000):
    qtbot.waitUntil(lambda: not win.runner.busy, timeout=timeout)


def cell(table, row, column):
    item = table.item(row, column)
    return item.text() if item else ""


def register_row(win, name):
    return win.mode.registers.index(name)


def test_load_shows_registers_memory_and_disassembly(window):
    assert window.load_source(LOOP, title="loop.asm")
    assert window.windowTitle().startswith("loop.asm")
    assert cell(window.registers.table, register_row(window, "ESP"), 2) == "007FFFFC"
    model = window.disassembly_model
    current = model.row_of(window.session.program.entry)
    assert model.data(model.index(current, 0)) == ">"
    assert window.memory_model.start == 0x0050_0000
    assert window.source.toPlainText() == LOOP
    texts = [row[2] for row in model.rows]
    assert "call WriteDec" in texts and "call exit" in texts


def test_single_step_marks_changed_registers(window, qtbot):
    window.load_source(LOOP)
    window.command("step")
    finish(qtbot, window)
    row = register_row(window, "ECX")
    assert cell(window.registers.table, row, 0) == "*"
    assert cell(window.registers.table, row, 2) == "00000003"
    assert cell(window.registers.table, register_row(window, "EBX"), 0) == ""
    assert window.session.current_line() == ADD_LINE
    assert window.source.current_line() == ADD_LINE


def test_run_to_the_end_shows_output(window, qtbot):
    window.load_source(LOOP)
    window.command("run")
    finish(qtbot, window)
    assert window.screen.output.toPlainText() == "6"
    assert "ended" in window.statusBar().currentMessage()
    assert not window.act["stop"].isEnabled() and window.act["run"].isEnabled()


def test_breakpoints_from_editor_disassembly_and_debug_panel(window, qtbot):
    window.load_source(LOOP, breakpoints=[ADD_LINE])
    assert window.source.breakpoint_lines() == [ADD_LINE]
    window.command("run")
    finish(qtbot, window)
    assert window.session.current_line() == ADD_LINE
    assert "breakpoint" in window.statusBar().currentMessage()
    assert window.debug.breakpoints.item(0).text() == f"line {ADD_LINE}"
    window.debug.breakpoints.setCurrentRow(0)
    window.debug._remove_breakpoint()
    assert window.session.breakpoint_lines == frozenset()
    assert window.source.breakpoint_lines() == []
    row = window.disassembly_model.row_of(window.session.program.line_to_address[LOOP_LINE])
    window._disassembly_double_clicked(window.disassembly_model.index(row, 0))
    assert window.session.breakpoint_lines == {LOOP_LINE}
    assert window.disassembly_model.data(window.disassembly_model.index(row, 0)) == "B"


def test_step_back_restores_registers(window, qtbot):
    window.load_source(LOOP)
    for _ in range(3):
        window.command("step")
        finish(qtbot, window)
    ecx = window.session.emulator.register("ECX")
    window.step_back()
    assert window.session.emulator.register("ECX") == ecx + 1
    assert cell(window.registers.table, register_row(window, "ECX"), 0) == "*"


def test_input_through_the_screen_window(window, qtbot):
    window.load_source(".code\nmain:\ncall ReadInt\ncall WriteInt\nexit")
    window.command("run")
    qtbot.waitUntil(lambda: window.screen.status.text() == "Waiting for input", timeout=5000)
    window.screen.input.setText("7")
    window.screen._submit()
    finish(qtbot, window)
    assert window.screen.output.toPlainText() == "7\n+7"


def test_ui_stays_responsive_during_a_million_steps(window, qtbot):
    window.load_source(".code\nmain:\ninc eax\njmp main")
    window.session.max_steps = 1_000_000
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(time.perf_counter()))
    timer.start(10)
    statuses = []
    window.statusBar().messageChanged.connect(statuses.append)
    start = time.perf_counter()
    window.command("run")
    finish(qtbot, window, timeout=30000)
    timer.stop()
    gaps = [b - a for a, b in zip(ticks, ticks[1:], strict=False)]
    assert window.session.emulator.total_steps == 1_000_000
    assert "step limit" in window.statusBar().currentMessage()
    assert len(ticks) >= 3
    assert max(gaps) < 0.25, f"event loop blocked for {max(gaps):.3f} s"
    assert any(s.startswith("Running...") for s in statuses)
    print(
        f"1,000,000 steps in {time.perf_counter() - start:.2f} s, longest UI gap {max(gaps):.3f} s"
    )


def test_stop_ends_a_run(window, qtbot):
    window.load_source(".code\nmain:\ninc eax\njmp main")
    window.session.max_steps = 10**12
    window.command("run")
    qtbot.wait(100)
    assert window.act["stop"].isEnabled()
    window.stop()
    finish(qtbot, window)
    assert window.statusBar().currentMessage().startswith("stopped at line")


def test_step_delay_mode_refreshes_between_steps(window, qtbot):
    window.load_source(LOOP)
    window.delay.setValue(20)
    seen = []
    window.runner.stepped.connect(lambda outcome: seen.append(outcome))
    window.command("run")
    qtbot.waitUntil(lambda: len(seen) >= 3, timeout=5000)
    qtbot.wait(60)  # at least one refresh tick between steps
    assert window.aux.trace.count() >= 1
    finish(qtbot, window)
    assert window.screen.output.toPlainText() == "6"


def test_edit_register(window, monkeypatch):
    window.load_source(LOOP)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("2A", True))
    window.edit_register("EAX")
    assert window.session.emulator.register("EAX") == 0x2A
    assert cell(window.registers.table, register_row(window, "EAX"), 0) == "*"


def test_memory_address_box(window):
    window.load_source(LOOP)
    window.address_box.setText("00700010")
    window.show_address()
    assert window.memory_model.start == 0x0070_0000
    assert window.memory_view.currentIndex().row() == 0x10
    window.address_box.setText("not hex")
    window.show_address()
    assert "hex" in window.statusBar().currentMessage()
    assert len(window.memory_model.values) == MemoryModel.WINDOW


def test_memory_changes_are_marked(window, qtbot):
    window.load_source(LOOP)
    window.command("step")
    finish(qtbot, window)
    window.command("step")  # add total, ecx
    finish(qtbot, window)
    model = window.memory_model
    assert model.data(model.index(0, 0)) == "*"
    assert model.data(model.index(0, 2)) == "03"
    assert model.data(model.index(4, 0)) == ""


def test_vars_stack_flags_and_watches(window, qtbot):
    window.load_source(LOOP)
    window.debug.watches.append("total * 2")
    for _ in range(2):
        window.command("step")
        finish(qtbot, window)
    vars_table = window.vars.table
    assert [cell(vars_table, 0, c) for c in range(6)] == [
        "*",
        "total",
        "00500000",
        "dword",
        "3",
        "00000003",
    ]
    assert cell(window.debug.watch_table, 0, 2) == "6"
    stack = window.stack.table
    esp_rows = [r for r in range(stack.rowCount()) if "ESP" in cell(stack, r, 0)]
    assert len(esp_rows) == 1
    assert cell(window.flags.table, 0, 1) == "CF"


def test_assembly_errors_are_shown_not_loaded(window):
    assert not window.load_source(".code\nfoo eax")
    assert "line 2: unknown instruction 'foo'" in window.messages[0]


def test_runtime_error_names_the_line(window, qtbot):
    window.load_source(".code\nmain:\nxor ecx, ecx\ndiv ecx")
    window.command("run")
    finish(qtbot, window)
    assert window.messages[0].startswith("line 4: divide error")


def test_cpu_structure_view_follows_steps(window, qtbot):
    window.load_source(".data\nv dd 10\n.code\nmain:\nmov eax, v\nadd eax, 5\nret")
    window.cpu.phase_mode.setChecked(True)
    window.command("step")
    finish(qtbot, window)
    assert [v.name for v in window.cpu.views] == ["Fetch", "Decode", "Execute", "Memory access"]
    assert window.cpu.views[-1].values["DR"].startswith("0000000A")
    assert window.cpu.diagram.view.name == "Fetch"
    for _ in range(3):
        window.cpu.next_phase()
    assert window.cpu.diagram.view.name == "Memory access"
    window.command("step")
    finish(qtbot, window)
    assert window.cpu.views[2].alu == "ADD A, 5 -> F"
    assert (
        "Simplified teaching model"
        in window.cpu.findChildren(type(window.cpu.phase_labels[0]))[-1].text()
    )


def test_projector_mode_and_uppercase(window):
    window.load_source(LOOP)
    size = window.registers.table.font().pointSizeF()
    window.act["projector"].setChecked(True)
    assert theme.current_name() == "contrast"
    assert window.registers.table.font().pointSizeF() > size
    window.act["projector"].setChecked(False)
    assert theme.current_name() != "contrast"
    assert window.registers.table.font().pointSizeF() == pytest.approx(size)
    window.act["uppercase"].setChecked(True)
    model = window.disassembly_model
    assert model.data(model.index(0, 3)).startswith("MOV")


def test_emulate_from_the_editor(qtbot, monkeypatch):
    editor = EditorWindow()
    monkeypatch.setattr(editor, "ask_unsaved", lambda doc: QMessageBox.Discard)
    qtbot.addWidget(editor)
    doc = editor.add_document(LOOP)
    doc.toggle_breakpoint(ADD_LINE)
    editor.emulate()
    emulator = editor.emulator
    try:
        assert emulator.isVisible()
        assert emulator.session.breakpoint_lines == {ADD_LINE}
        doc.setPlainText(LOOP.replace("mov  ecx, 3", "mov  ecx, 4"))
        emulator.reload()
        emulator.command("run")
        finish(qtbot, emulator)
        emulator.session.toggle_breakpoint(ADD_LINE)
        emulator.command("run")
        finish(qtbot, emulator)
        assert emulator.screen.output.toPlainText() == "10"
    finally:
        emulator.close()
        emulator.shutdown()
