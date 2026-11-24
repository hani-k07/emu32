"""DOS and BIOS services in COM programs (spec 8.2, 13.1)."""

import datetime

import pytest

from emu32.emulator import StopReason
from emu32.session import Session


def run(source: str, typed: str = "") -> Session:
    session = Session()
    session.load(source)
    session.console.feed(typed)
    outcome = session.run()
    assert outcome.reason is StopReason.EXITED, outcome.message
    return session


def regs(session: Session) -> dict[str, int]:
    return session.emulator.registers()


BUFFERED = """\
org 100h
    mov dx, offset buffer
    mov ah, 0Ah
    int 21h
    mov dl, 10
    mov ah, 2
    int 21h
    mov bl, buffer[1]           ; how many characters were typed
    mov bh, 0
    mov byte ptr buffer[bx+2], '$'
    mov dx, offset buffer + 2
    mov ah, 9
    int 21h
    ret
buffer db 6, ?, 6 dup(0)
"""


READ_ONLY = """\
org 100h
    mov dx, offset buffer
    mov ah, 0Ah
    int 21h
    ret
buffer db 6, ?, 6 dup(0)
"""


def test_buffered_input_fills_count_characters_and_cr():
    assert run(BUFFERED, "Ali\n").console.output() == "Ali\nAli"
    session = run(READ_ONLY, "Ali\n")
    address = session.program.symbols["buffer"].address
    assert session.read_bytes(address, 6) == [6, 3, ord("A"), ord("l"), ord("i"), 0x0D]


def test_buffered_input_stops_at_the_buffer_size():
    session = run(READ_ONLY, "abcdefgh\n")
    address = session.program.symbols["buffer"].address
    # Room for 5 characters and the CR.
    assert session.read_bytes(address, 8) == [6, 5, *b"abcde", 0x0D]
    assert session.console.output() == "abcde"


def test_buffered_input_with_size_zero_is_an_error():
    session = Session()
    session.load("org 100h\nmov dx, offset b\nmov ah, 0Ah\nint 21h\nret\nb db 0, 0\n")
    session.console.feed("x\n")
    outcome = session.run()
    assert outcome.reason is StopReason.ERROR
    assert "byte 0 of the buffer is 0" in outcome.message and "line 4" in outcome.message


def test_read_with_echo_and_without_echo():
    source = "org 100h\nmov ah, 1\nint 21h\nmov bl, al\nmov ah, 8\nint 21h\nmov bh, al\nret\n"
    session = run(source, "xy")
    assert session.console.output() == "x"  # 08h does not echo
    assert regs(session)["BX"] == ord("y") << 8 | ord("x")


def test_enter_reads_as_carriage_return():
    assert regs(run("org 100h\nmov ah, 7\nint 21h\nret\n", "\n"))["AX"] & 0xFF == 0x0D


def test_direct_console_io():
    source = """\
org 100h
    mov ah, 6
    mov dl, 0FFh
    int 21h            ; nothing typed yet: ZF = 1, AL = 0
    lahf
    mov bl, ah
    mov ah, 6
    mov dl, 'Q'
    int 21h            ; output
    ret
"""
    session = run(source)
    assert session.console.output() == "Q"
    assert regs(session)["BX"] & 0x40  # ZF was set


def test_direct_console_input_without_waiting():
    session = run("org 100h\nmov ah, 6\nmov dl, 0FFh\nint 21h\nret\n", "k")
    assert regs(session)["AX"] & 0xFF == ord("k")
    assert not session.emulator.flags()["ZF"]


def test_date_and_time():
    today = datetime.date.today()
    session = run(
        "org 100h\nmov ah, 2Ah\nint 21h\nmov si, cx\nmov di, dx\nmov ah, 2Ch\nint 21h\nret\n"
    )
    registers = regs(session)
    assert registers["SI"] == today.year
    assert registers["DI"] == today.month << 8 | today.day
    assert registers["CX"] >> 8 < 24 and registers["CX"] & 0xFF < 60


def test_teletype_and_set_mode():
    source = """\
org 100h
    mov ah, 0Eh
    mov al, 'A'
    int 10h
    mov ax, 3          ; set video mode 3: clears the screen
    int 10h
    mov ah, 0Eh
    mov al, 'B'
    int 10h
    ret
"""
    assert run(source).console.output() == "B"


def test_int_16h_wait_for_key_gives_scan_code_and_character():
    session = run("org 100h\nmov ah, 0\nint 16h\nret\n", "a")
    assert regs(session)["AX"] == 0x1E61  # 'a' is scan code 1Eh


def test_int_16h_check_for_key_leaves_it_waiting():
    source = "org 100h\nmov ah, 1\nint 16h\nmov bx, ax\nmov ah, 0\nint 16h\nret\n"
    session = run(source, "\n")
    assert regs(session)["BX"] == 0x1C0D == regs(session)["AX"]  # Enter, still there for 00h


def test_int_16h_check_with_no_key_sets_zf():
    run_session = run("org 100h\nmov ah, 1\nint 16h\nret\n")
    assert run_session.emulator.flags()["ZF"] == 1


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("mov ah, 7Fh\nint 21h", "int 21h function 7Fh is not supported yet"),
        ("mov ah, 0Ch\nint 10h", "int 10h function 0Ch is not supported yet"),
        ("mov ah, 5\nint 16h", "int 16h function 05h is not supported yet"),
        ("mov ah, 3\nint 33h", "int 33h function 03h is not supported yet"),
    ],
)
def test_unsupported_functions_name_interrupt_function_and_line(code, message):
    session = Session()
    session.load(f"org 100h\n{code}\nret\n")
    outcome = session.run()
    assert outcome.reason is StopReason.ERROR
    assert message in outcome.message and "line 3" in outcome.message


def test_waiting_input_can_be_stopped_and_resumed():
    session = Session()
    session.load(BUFFERED)
    import threading

    result = {}
    worker = threading.Thread(target=lambda: result.setdefault("outcome", session.run()))
    worker.start()
    for _ in range(200):
        if session.console.waiting:
            break
        threading.Event().wait(0.01)
    assert session.console.waiting
    session.console.cancel()
    worker.join(5)
    assert result["outcome"].reason is StopReason.STOPPED
    session.console.feed("ok\n")
    assert session.run().reason is StopReason.EXITED
    assert session.console.output().endswith("ok")
