import threading

import pytest

from emu32.assembler import AssemblyError, assemble
from emu32.emulator import Emulator, StopReason
from emu32.runtime import Console, attach


def start(source, intel_syntax=False):
    emu, console = Emulator(), Console()
    externals = attach(emu, console)
    program = assemble(source, intel_syntax=intel_syntax, externals=externals)
    emu.load(program.code, program.data, program.entry)
    return emu, console, program


def run(source, typed="", intel_syntax=False):
    emu, console, program = start(source, intel_syntax)
    console.feed(typed)
    return emu, emu.run(), console.output()


def library(body, data=""):
    return (
        f"INCLUDE Irvine32.inc\n.data\n{data}\n.code\nmain PROC\n{body}\nexit\nmain ENDP\nEND main"
    )


# Acceptance: hello world in both syntax styles


def test_hello_world_masm_style():
    source = """
    INCLUDE Irvine32.inc
    .data
    greeting BYTE "Hello, world!", 0
    .code
    main PROC
        mov  edx, OFFSET greeting
        call WriteString
        call Crlf
        exit
    main ENDP
    END main
    """
    _, result, output = run(source)
    assert result.reason is StopReason.EXITED
    assert output == "Hello, world!\n"


def test_hello_world_intel_style():
    source = """
    section .data
    greeting db 'Hello, world!', 13, 10, '$'
    section .text
    _start:
        mov edx, greeting
        mov ah, 9
        int 21h
        mov ah, 4Ch
        int 21h
    """
    _, result, output = run(source, intel_syntax=True)
    assert result.reason is StopReason.EXITED
    assert output == "Hello, world!\n"


def test_hello_world_dos_layout():
    source = """
    .model small
    .stack 100h
    .data
    msg db "Hello, world!$"
    .code
    main proc
        mov edx, offset msg
        mov ah, 09h
        int 21h
        mov ah, 4ch
        mov al, 0
        int 21h
    main endp
    end main
    """
    emu, result, output = run(source)
    assert (result.reason, emu.exit_code, output) == (StopReason.EXITED, 0, "Hello, world!")


# Acceptance: ReadInt round trip


@pytest.mark.parametrize(("typed", "printed"), [("42", "+42"), ("-7", "-7"), ("  15 ", "+15")])
def test_read_int_round_trip(typed, printed):
    emu, _, output = run(library("call ReadInt\ncall WriteInt"), typed=f"{typed}\n")
    assert output == f"{typed}\n{printed}"  # the typed line is echoed
    assert emu.flags()["OF"] == 0


@pytest.mark.parametrize("typed", ["abc", "3000000000", ""])
def test_read_int_rejects_bad_input(typed):
    emu, _, _ = run(library("mov eax, 99\ncall ReadInt\nmov ebx, eax"), typed=f"{typed}\n")
    assert emu.register("EBX") == 0
    assert emu.flags()["OF"] == 1


def test_input_blocks_until_typed():
    emu, console, _ = start(library("call ReadInt\ncall WriteInt"))
    waiting = threading.Event()
    console.on_wait = lambda value: value and waiting.set()
    worker = threading.Thread(target=lambda: setattr(worker, "result", emu.run()))
    worker.start()
    assert waiting.wait(5)
    assert console.waiting
    console.feed("8\n")
    worker.join(5)
    assert worker.result.reason is StopReason.EXITED
    assert console.output() == "8\n+8"
    assert not console.waiting


@pytest.mark.parametrize(
    "body",
    ["call ReadInt\ncall WriteInt", "mov ah, 1\nint 21h\nmov ah, 2\nmov dl, al\nint 21h"],
)
def test_cancelled_input_stops_and_retries_on_next_run(body):
    emu, console, _ = start(library(body))
    waiting = threading.Event()
    console.on_wait = lambda value: value and waiting.set()
    worker = threading.Thread(target=lambda: setattr(worker, "result", emu.run()))
    worker.start()
    assert waiting.wait(5)
    console.cancel()
    worker.join(5)
    assert worker.result.reason is StopReason.STOPPED
    console.feed("5\n")
    assert emu.run().reason is StopReason.EXITED
    assert console.output().endswith("5")


# Library routines


def test_write_routines():
    body = """
    mov eax, -42
    call WriteInt
    call Crlf
    call WriteDec
    call Crlf
    call WriteHex
    call Crlf
    mov eax, 5
    call WriteInt
    mov al, 'x'
    call WriteChar
    """
    _, _, output = run(library(body))
    assert output == "-42\n4294967254\nFFFFFFD6\n+5x"


def test_read_string_limits_and_terminates():
    body = "mov edx, OFFSET buf\nmov ecx, SIZEOF buf\ncall ReadString"
    emu, result, output = run(library(body, data="buf db 6 dup(0FFh)"), typed="abcdefgh\n")
    assert emu.register("EAX") == 5
    assert emu.read_memory(0x0050_0000, 6) == b"abcde\x00"
    assert output == "abcdefgh\n"


def test_read_char_does_not_echo_and_enter_is_cr():
    emu, _, output = run(library("call ReadChar\nmov bl, al\ncall ReadChar"), typed="q\n")
    assert (emu.register("BL"), emu.register("AL"), output) == (ord("q"), 0x0D, "")


def test_dump_regs_shows_caller_view():
    _, _, output = run(library("mov eax, 1234ABCDh\ncall DumpRegs"))
    assert "EAX=1234ABCD" in output
    assert "ESP=007FFFFC" in output  # as before the call
    assert "ZF=0" in output and "IF=1" in output


def test_exit_process_returns_code():
    emu, result, _ = run(library("push 7\ncall ExitProcess\nmov eax, 1"))
    assert (result.reason, emu.exit_code, emu.register("EAX")) == (StopReason.EXITED, 7, 0)


def test_bad_string_pointer_is_reported_at_the_call():
    emu, console, program = start(library("mov edx, 12345678h\ncall WriteString"))
    result = emu.run()
    call_address = program.line_to_address[7]
    assert result.reason is StopReason.ERROR
    assert "WriteString" in result.message and "outside" in result.message
    assert call_address <= result.address < call_address + 5


def test_routine_names_are_reserved():
    with pytest.raises(AssemblyError, match="built-in routine"):
        start(".code\nWriteString PROC\nret\nWriteString ENDP")


def test_extended_characters_use_code_page_437():
    _, _, output = run(library("mov al, 0DBh\ncall WriteChar"))
    assert output == "█"


# int 21h services


def test_int21_read_char_echoes():
    emu, _, output = run(library("mov ah, 1\nint 21h"), typed="k")
    assert (emu.register("AL"), output) == (ord("k"), "k")


def test_int21_print_signed_extension():
    _, _, output = run(library("mov edx, -15\nmov ah, 40h\nint 21h"))
    assert output == "-15"


@pytest.mark.parametrize(
    ("body", "text"),
    [
        ("mov ah, 7Fh\nint 21h", "function 7Fh is not supported"),
        ("mov edx, OFFSET s\nmov ah, 9\nint 21h", "no terminating '$'"),
    ],
)
def test_int21_errors_point_at_the_int(body, text):
    emu, console, program = start(library(body, data="s db 'no dollar'"))
    result = emu.run()
    assert result.reason is StopReason.ERROR
    assert text in result.message
    int_line = 7 if "OFFSET" not in body else 8
    assert result.address == program.line_to_address[int_line]


def test_cut_off_address_gets_a_hint():
    emu, _, _ = start(library("xor edx, edx\nmov dx, 18h\nmov ah, 9\nint 21h"))
    result = emu.run()
    assert result.reason is StopReason.ERROR
    assert "mov edx, OFFSET message" in result.message
