"""The 80 x 25 text screen and the int 10h services that draw on it (spec 8.3)."""

from emu32.emulator import StopReason
from emu32.runtime.screen import COLUMNS, ROWS, TextScreen
from emu32.session import Session


def cell(screen: TextScreen, row: int, column: int) -> tuple[str, int]:
    return screen.cells[row * COLUMNS + column]


def test_teletype_handles_cr_lf_backspace_and_tab():
    screen = TextScreen()
    screen.teletype("ab\rX\nc\bd\te")
    assert screen.text() == "Xb\nd       e"
    assert screen.cursor() == (1, 9)


def test_line_feed_only_moves_down_in_com_programs():
    source = (
        "org 100h\nmov ah, 2\n"
        + "".join(f"mov dl, {c}\nint 21h\n" for c in ("'a'", "10", "'b'", "13", "10", "'c'"))
        + "ret\n"
    )
    assert run(source).console.screen.text() == "a\n b\nc"


def test_teletype_wraps_and_scrolls():
    screen = TextScreen()
    screen.teletype("x" * COLUMNS + "y")
    assert screen.cursor() == (1, 1) and cell(screen, 1, 0) == ("y", 0x07)
    screen = TextScreen()
    screen.teletype("".join(f"{n}\n" for n in range(ROWS)))
    lines = screen.text().split("\n")
    assert lines[0] == "1" and lines[-1] == str(ROWS - 1)  # line "0" scrolled off


def test_step_snapshot_only_when_the_screen_changes():
    screen = TextScreen()
    screen.begin_step()
    assert screen.end_step() is None
    screen.begin_step()
    screen.teletype("hi")
    before = screen.end_step()
    assert before is not None
    screen.restore(before)
    assert screen.text() == "" and screen.cursor() == (0, 0)


def run(source: str) -> Session:
    session = Session()
    session.load(source)
    outcome = session.run()
    assert outcome.reason is StopReason.EXITED, outcome.message
    return session


def test_set_and_get_cursor():
    source = """\
org 100h
    mov ah, 2
    mov dh, 5           ; row
    mov dl, 10          ; column
    int 10h
    mov ah, 0Eh
    mov al, '*'
    int 10h
    mov ah, 3
    int 10h
    ret
"""
    session = run(source)
    screen = session.console.screen
    assert cell(screen, 5, 10) == ("*", 0x07)
    registers = session.emulator.registers()
    assert registers["DX"] == 5 << 8 | 11 and registers["CX"] == 0x0607


def test_write_character_with_attribute_keeps_the_cursor():
    source = "org 100h\nmov ah, 9\nmov al, 'Z'\nmov bl, 1Eh\nmov cx, 3\nint 10h\nret\n"
    screen = run(source).console.screen
    assert [cell(screen, 0, c) for c in range(3)] == [("Z", 0x1E)] * 3
    assert screen.cursor() == (0, 0)


def test_write_string_with_one_color_and_moving_cursor():
    source = """\
org 100h
    mov ax, 1301h       ; AL = 1: move the cursor
    mov bx, 0004h       ; BL = 4: red on black
    mov cx, 5
    mov dx, 0203h       ; row 2, column 3
    mov bp, offset text
    int 10h
    ret
text db 'Hello'
"""
    session = run(source)
    screen = session.console.screen
    assert "".join(cell(screen, 2, 3 + i)[0] for i in range(5)) == "Hello"
    assert cell(screen, 2, 3)[1] == 0x04 and screen.cursor() == (2, 8)
    assert session.console.output() == "Hello"  # the Output tab keeps the text too


def test_write_string_with_a_color_per_character():
    source = """\
org 100h
    mov ax, 1302h       ; AL = 2: color bytes in the string, cursor stays
    mov cx, 2
    mov dx, 0000h
    mov bp, offset text
    int 10h
    ret
text db 'A', 1Fh, 'B', 2Eh
"""
    screen = run(source).console.screen
    assert cell(screen, 0, 0) == ("A", 0x1F) and cell(screen, 0, 1) == ("B", 0x2E)
    assert screen.cursor() == (0, 0)


def test_scroll_window_up_and_clear():
    source = """\
org 100h
    mov ah, 9
    mov al, 'a'
    mov bl, 7
    mov cx, 80
    int 10h             ; row 0 full of 'a'
    mov ax, 0601h       ; scroll rows 0-1 up by one
    mov bh, 70h         ; new line: black on gray
    mov cx, 0000h
    mov dx, 014Fh
    int 10h
    ret
"""
    screen = run(source).console.screen
    assert cell(screen, 0, 0) == (" ", 0x07)  # row 1 (blank) moved up
    assert cell(screen, 1, 0) == (" ", 0x70)  # the new line has BH's color


def test_flat_library_gotoxy_and_set_text_color():
    source = """\
INCLUDE Irvine32.inc
.data
msg BYTE "hi", 0
.code
main PROC
    mov eax, 14 + 16 * 1     ; yellow on blue
    call SetTextColor
    mov dh, 3
    mov dl, 4
    call Gotoxy
    mov edx, OFFSET msg
    call WriteString
    exit
main ENDP
END main
"""
    screen = run(source).console.screen
    assert cell(screen, 3, 4) == ("h", 0x1E) and cell(screen, 3, 5) == ("i", 0x1E)


def test_step_back_restores_the_screen():
    session = Session()
    session.load("org 100h\nmov ah, 2\nmov dl, 'Q'\nint 21h\nret\n")
    for _ in range(3):
        session.step()
    assert session.console.screen.text() == "Q"
    assert session.step_back()
    assert session.console.screen.text() == "" and session.console.screen.cursor() == (0, 0)


def test_screen_grid_shows_output_and_sends_keys(qtbot):
    from PySide6.QtCore import Qt

    from emu32.gui.emulator_window import EmulatorWindow

    window = EmulatorWindow()
    qtbot.addWidget(window)
    window.show()
    try:
        assert window.load_source("org 100h\nmov ah, 1\nint 21h\nret\n", title="key.asm")
        window.command("run")
        qtbot.waitUntil(lambda: window.screen.status.text() == "Waiting for input", timeout=5000)
        window.screen.view.setFocus()
        qtbot.keyClick(window.screen.view, Qt.Key_K)
        qtbot.waitUntil(lambda: not window.runner.busy, timeout=5000)
        window.refresh()
        assert window.screen.view.text() == "k"
        assert window.screen.output.toPlainText() == "k"
    finally:
        window.shutdown()
