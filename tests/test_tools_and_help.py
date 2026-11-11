import pytest
from PySide6.QtWidgets import QMessageBox

from emu32.emulator import StopReason
from emu32.gui import settings
from emu32.gui.editor_window import EditorWindow
from emu32.gui.emulator_window import EmulatorWindow
from emu32.gui.help_window import PAGES, HelpWindow, page_text
from emu32.gui.tools import AsciiDialog, CalculatorDialog, ConverterDialog
from emu32.session import Session


def test_converter(qtbot):
    dialog = ConverterDialog()
    qtbot.addWidget(dialog)
    dialog.bits.setCurrentIndex(0)  # 8 bits
    dialog.value.setText("-1")
    assert dialog.labels["hex"].text() == "FF"
    assert dialog.labels["dec_unsigned"].text() == "255"
    assert dialog.labels["dec_signed"].text() == "-1"
    assert dialog.labels["bin"].text() == "1111 1111"
    dialog.base.setCurrentIndex(dialog.base.findData("bin"))
    dialog.value.setText("1012")
    assert "base-2" in dialog.message.text()
    dialog.value.setText("100000000")
    assert "does not fit in 8 bits" in dialog.message.text()


def test_calculator(qtbot):
    dialog = CalculatorDialog()
    qtbot.addWidget(dialog)
    dialog.expression.setText("(0FFh and 1010b) shl 2")
    assert dialog.labels["hex"].text() == "00000028"
    assert dialog.message.text() == "Result: 40"
    dialog.expression.setText("1 / 0")
    assert dialog.message.text() == "division by zero"


def test_ascii_table(qtbot):
    dialog = AsciiDialog()
    qtbot.addWidget(dialog)
    assert (dialog.table.rowCount(), dialog.table.columnCount()) == (32, 8)
    assert dialog.code_at(65) == " 65 41 A"
    assert dialog.code_at(0) == "  0 00 NULL"
    assert dialog.code_at(219) == "219 DB █"
    assert "hex 41h" in dialog.detail.text()
    dialog.table.setCurrentCell(10, 0)
    assert dialog.detail.text().startswith("LF")


@pytest.mark.parametrize("key", list(PAGES))
def test_help_pages_load(qtbot, key):
    window = HelpWindow()
    qtbot.addWidget(window)
    window.show_page(key)
    assert PAGES[key] in window.windowTitle()
    assert window.text.toPlainText().strip()


def test_quick_start_states_the_step_back_limit():
    assert "10,000" in page_text("quickstart")


def test_constructs_from_the_syntax_reference_work():
    source = """INCLUDE Irvine32.inc
.data
count   DWORD 0
small   BYTE  -1
table   WORD  1, 2, 3
text    BYTE  "Hello", 13, 10, 0
buffer  BYTE  80 DUP(0)
grid    DWORD 3 DUP(4 DUP(?))
temp    SDWORD -40
LIMIT   EQU 100
step    = 4
textlen = $ - text
.code
main PROC
    mov  ax, table[4]
    mov  bx, [table + 2]
    mov  ecx, LENGTHOF table
    add  ecx, SIZEOF table
    add  ecx, TYPE table
    mov  al, BYTE PTR count
    inc  small
    mov  esi, OFFSET text
    mov  edx, LIMIT + step
    stc
    cmc
    push 1
    call two
    exit
main ENDP
two PROC
    ret 4
two ENDP
END main
"""
    session = Session()
    program = session.load(source)
    assert program.symbols["grid"].count == 12
    assert program.constants["textlen"] == 8 + 80 + 12 * 4 + 4  # text, buffer, grid, temp
    outcome = session.run()
    assert outcome.reason is StopReason.EXITED
    emu = session.emulator
    assert (emu.register("BX"), emu.register("ECX")) == (2, 3 + 6 + 2)
    assert emu.register("EDX") == 104
    assert emu.flags()["CF"] == 0
    assert session.evaluate("small") == 0


def test_menus_open_tools_and_help(qtbot, monkeypatch):
    editor = EditorWindow()
    monkeypatch.setattr(editor, "ask_unsaved", lambda doc: QMessageBox.Discard)
    qtbot.addWidget(editor)
    for key in ("calculator", "converter", "ascii", "tutorial", "reference", "instructions"):
        assert editor.act[key].isEnabled()
        editor.act[key].trigger()
    assert editor._tool_windows["calculator"].isVisible()
    assert editor._help_window.windowTitle().startswith("Instruction reference")

    emulator = EmulatorWindow()
    qtbot.addWidget(emulator)
    try:
        emulator.act["converter"].trigger()
        emulator.act["syntax"].trigger()
        assert emulator._tool_windows["converter"].isVisible()
        assert emulator._help_window.windowTitle().startswith("Syntax reference")
    finally:
        emulator.shutdown()


def test_window_layout_is_remembered(qtbot):
    first = EmulatorWindow()
    qtbot.addWidget(first)
    first.docks["Vars"].show()
    first.close()
    first.shutdown()
    assert settings.settings().value("emulator_state") is not None
    second = EmulatorWindow()
    qtbot.addWidget(second)
    try:
        assert not second.docks["Vars"].isHidden()
    finally:
        second.shutdown()


def test_about_lists_every_engine_with_a_version(qtbot):
    from emu32.gui.dialogs import AboutDialog, component_versions

    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    parts = component_versions()
    assert [p[0].split()[0] for p in parts] == ["Unicorn", "Keystone", "Capstone", "Qt", "Python"]
    assert all(version for _, version, _ in parts)
