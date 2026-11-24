"""COM and EXE program models: detection, layout and 8086 behavior (spec 6, 7.4, 13.1)."""

import pytest

from emu32.assembler import assemble
from emu32.assembler.cleaner import clean
from emu32.assembler.encode import detect_model
from emu32.emulator import StopReason
from emu32.session import Session


def model_of(source: str) -> str:
    return detect_model(clean(source)[0]).key


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("org 100h\nret\n", "com"),
        ("mov ax, 5\nret\n", "com"),  # no model directive at all
        ("#make_com#\nmov ax, 5\nret\n", "com"),
        ("#make_exe#\n.data\n.code\nmain proc\nret\nmain endp\nend main\n", "exe"),
        (".model small\n.stack 100h\n.data\n.code\nmain proc\nret\nmain endp\nend main\n", "exe"),
        (".model tiny\n.code\nret\n", "exe"),
        (".386\n.model small\n.code\nret\n", "exe"),
        (".386\n.model flat\n.code\nmain proc\nret\nmain endp\nend main\n", "flat"),
        ("INCLUDE Irvine32.inc\n.code\nmain proc\nexit\nmain endp\nend main\n", "flat"),
        (".data\nx dd 1\n.code\nmain proc\nret\nmain endp\nend main\n", "flat"),
    ],
)
def test_model_detection(source, expected):
    assert model_of(source) == expected


def run(source: str, steps: int | None = None, feed: str = "") -> Session:
    session = Session()
    session.load(source)
    if feed:
        session.console.feed(feed)
    if steps is None:
        outcome = session.run()
        assert outcome.reason is StopReason.EXITED, outcome.message
    else:
        for _ in range(steps):
            session.step()
    return session


def regs(session: Session) -> dict[str, int]:
    return session.emulator.registers()


HELLO_COM = """\
org 100h
mov dx, offset msg
mov ah, 09h
int 21h
ret
msg db "Hello, COM$"
"""


def test_com_hello_world_and_ret_ends_the_program():
    session = run(HELLO_COM)
    assert session.mode.key == "com"
    assert session.console.output() == "Hello, COM"
    program = session.program
    # Everything sits in one image at 100h; the data follows `ret` (C3) directly.
    assert program.code_base == 0x100 and program.entry == 0x100
    assert program.code[:3] == bytes([0xBA, 0x08, 0x01])  # mov dx, 0108h
    assert program.code[7] == 0xC3 and program.code[8:] == b"Hello, COM$"


def test_com_data_before_code_stays_in_place():
    source = (
        "org 100h\njmp start\nmsg db 'Hi$'\nstart:\nmov dx, offset msg\nmov ah, 9\nint 21h\nret\n"
    )
    session = run(source)
    assert session.console.output() == "Hi"
    assert session.program.symbols["msg"].address == 0x102  # after the 2-byte jmp short


def test_com_initial_state_matches_dos():
    session = Session()
    session.load(HELLO_COM)
    registers = regs(session)
    assert registers["IP"] == 0x100 and registers["SP"] == 0xFFFE
    assert all(registers[s] == 0 for s in ("CS", "DS", "ES", "SS"))
    assert session.read_bytes(0, 2) == [0xCD, 0x20]  # int 20h, as at the start of the PSP
    assert session.read_bytes(0xFFFE, 2) == [0, 0]  # `ret` goes to offset 0


def test_int_20h_ends_the_program():
    session = run("org 100h\nmov ax, 1\nint 20h\nmov ax, 2\n")
    assert regs(session)["AX"] == 1


def test_exe_hello_world_with_data_segment():
    source = """\
.model small
.stack 100h
.data
msg db 'Hello, EXE$'
.code
main proc
    mov ax, @data
    mov ds, ax
    mov dx, offset msg
    mov ah, 09h
    int 21h
    mov ah, 4Ch
    int 21h
main endp
end main
"""
    session = run(source)
    assert session.mode.key == "exe"
    assert session.console.output() == "Hello, EXE"
    program = session.program
    # .data at 100h, code from the next 16-byte boundary (D81); @data is 0.
    assert program.symbols["msg"].address == 0x100
    assert program.code_base == 0x110 and program.entry == 0x110
    assert regs(session)["DS"] == 0


def test_bp_parameter_pattern_uses_a_two_byte_return_address():
    source = """\
org 100h
    push 9
    push 4
    call minus
    add sp, 4
    ret
minus proc
    push bp
    mov bp, sp
    mov ax, [bp+6]      ; first push
    sub ax, [bp+4]      ; second push
    pop bp
    ret
minus endp
"""
    session = run(source)
    assert regs(session)["AX"] == 5
    listing = {text: blob for _a, blob, text, _l in session.listing()}
    assert listing["push 9"] == bytes([0x6A, 0x09])  # a word, not a dword
    assert listing["call minus"][0] == 0xE8 and len(listing["call minus"]) == 3
    assert listing["ret"] == bytes([0xC3])


def test_call_pushes_two_bytes():
    session = Session()
    session.load("org 100h\ncall f\nret\nf:\nret\n")
    session.step()
    assert regs(session)["SP"] == 0xFFFC
    assert session.read_bytes(0xFFFC, 2) == [0x03, 0x01]  # return to 0103h


def test_loop_with_cx_zero_runs_65536_times_and_keeps_ecx_high_half():
    source = "org 100h\nmov ecx, 12340000h\nxor bx, bx\nagain:\ninc bx\nloop again\nret\n"
    session = run(source)
    registers = regs(session)
    assert registers["BX"] == 0  # 65,536 increments of a 16-bit register
    assert registers["ECX"] == 0x1234_0000


def test_jcxz_tests_cx():
    source = "org 100h\nmov ecx, 10000h\nmov ax, 1\njcxz done\nmov ax, 2\ndone:\nret\n"
    assert regs(run(source))["AX"] == 1


def test_rep_movsb_uses_cx_si_di():
    source = """\
org 100h
    mov si, offset src
    mov di, offset dst
    mov cx, 3
    cld
    rep movsb
    mov dx, offset dst
    mov ah, 9
    int 21h
    ret
src db 'abc'
dst db 3 dup('-'), '$'
"""
    session = run(source)
    assert session.console.output() == "abc"
    assert regs(session)["CX"] == 0


def test_pusha_pushes_sixteen_bytes():
    session = Session()
    session.load("org 100h\npusha\nret\n")
    session.step()
    assert regs(session)["SP"] == 0xFFFE - 16


@pytest.mark.parametrize(
    ("setup", "flags"),
    [
        ("mov ax, 7FFFh\nadd ax, 1", {"OF": 1, "CF": 0, "SF": 1}),
        ("mov ax, 0FFFFh\nadd ax, 1", {"CF": 1, "ZF": 1, "OF": 0}),
        ("mov ax, 8000h\nsub ax, 1", {"OF": 1, "CF": 0}),
        ("mov ax, 0\nsub ax, 1", {"CF": 1, "SF": 1}),
    ],
)
def test_sixteen_bit_flags(setup, flags):
    session = Session()
    session.load(f"org 100h\n{setup}\nret\n")
    session.step()
    session.step()
    actual = session.emulator.flags()
    assert {name: actual[name] for name in flags} == flags


def test_mul_and_div_with_dx_ax():
    session = run("org 100h\nmov ax, 1000h\nmov bx, 20h\nmul bx\nmov cx, ax\nmov si, dx\nret\n")
    assert regs(session)["SI"] == 0x0002 and regs(session)["CX"] == 0x0000
    session = run("org 100h\nmov dx, 2\nmov ax, 3\nmov bx, 10h\ndiv bx\nret\n")
    assert regs(session)["AX"] == 0x2000 and regs(session)["DX"] == 3


def test_divide_error_names_the_line():
    session = Session()
    session.load("org 100h\nmov ax, 1\nmov bl, 0\ndiv bl\nret\n")
    outcome = session.run()
    assert outcome.reason is StopReason.ERROR
    assert "line 4" in outcome.message


def test_cbw_and_cwd():
    session = run("org 100h\nmov al, 80h\ncbw\nmov bx, ax\ncwd\nret\n")
    assert regs(session)["BX"] == 0xFF80 and regs(session)["DX"] == 0xFFFF
    listing = [text for _a, _b, text, _l in session.listing()]
    assert "cbw" in listing and "cwd" in listing


def test_thirty_two_bit_registers_in_a_com_program():
    session = run("org 100h\nmov eax, 100000\nmov ebx, 3\nmul ebx\nret\n")
    assert regs(session)["EAX"] == 300_000 and regs(session)["AX"] == 300_000 & 0xFFFF


def test_location_counter_in_com_data():
    source = """\
org 100h
    mov cx, len
    mov si, offset msg
next:
    mov dl, [si]
    mov ah, 2
    int 21h
    inc si
    loop next
    ret
msg db 'abc'
len equ $ - msg
"""
    assert run(source).console.output() == "abc"


def test_breakpoint_after_data_in_the_middle():
    source = "org 100h\njmp start\nmsg db 'Hi$'\nstart:\nmov ax, 1\nmov bx, 2\nret\n"
    session = Session()
    session.load(source)
    session.toggle_breakpoint(6)
    outcome = session.run()
    assert outcome.reason is StopReason.BREAKPOINT
    assert session.current_line() == 6 and regs(session)["AX"] == 1


def test_session_switches_between_models():
    session = Session()
    session.load(".386\n.model flat\n.code\nmain proc\nmov eax, 1\nret\nmain endp\nend main\n")
    assert session.mode.key == "flat"
    session.load(HELLO_COM)
    assert session.mode.key == "com"
    session.run()
    assert session.console.output() == "Hello, COM"
    session.load(".386\n.model flat\n.code\nmain proc\nmov eax, 1\nret\nmain endp\nend main\n")
    assert session.mode.key == "flat" and session.run().reason is StopReason.EXITED


def test_step_back_restores_32_bit_registers_in_a_com_program():
    session = Session()
    session.load("org 100h\nmov eax, 12345678h\nmov ax, 1\nret\n")
    session.step()
    session.step()
    assert session.step_back()
    assert regs(session)["EAX"] == 0x1234_5678


def test_flat_only_constructs_explain_the_com_way():
    from emu32.assembler.errors import AssemblyError

    with pytest.raises(AssemblyError) as error:
        assemble("org 100h\nf proc x:word\nret\nf endp\n", mode=None)
    assert "[bp+4]" in str(error.value.errors[0])


def test_xlat_and_retn_spellings():
    source = (
        "org 100h\nmov bx, offset table\nmov al, 2\nxlat\ncall f\nret\n"
        "f proc\nretn\nf endp\ntable db 10, 20, 30\n"
    )
    assert regs(run(source))["AX"] & 0xFF == 30


def test_in_and_out_warn_once_and_in_reads_zero():
    session = Session()
    program = session.load("org 100h\nmov ax, 0FFFFh\nin al, 60h\nout 61h, al\nret\n")
    assert [w.line for w in program.warnings] == [3]
    session.run()
    assert regs(session)["AX"] == 0xFF00
