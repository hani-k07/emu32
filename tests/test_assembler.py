from pathlib import Path

import pytest
from conftest import CODE, DATA

from emu32.assembler import AssemblyError, assemble
from emu32.emulator import Emulator, StopReason

EXAMPLES = Path(__file__).parent.parent / "examples"


def run(source, intel_syntax=False, max_steps=None):
    program = assemble(source, intel_syntax=intel_syntax)
    emu = Emulator()
    emu.load(program.code, program.data, program.entry)
    return program, emu, emu.run(max_steps)


def errors_of(source, **kwargs):
    with pytest.raises(AssemblyError) as info:
        assemble(source, **kwargs)
    return [(e.line, e.text) for e in info.value.errors]


def dword(emu, address):
    return int.from_bytes(emu.read_memory(address, 4), "little")


# Acceptance: the array-sum example


def test_sum_array_example_runs_to_the_right_answer():
    program, emu, result = run((EXAMPLES / "sum_array.asm").read_text(encoding="utf-8"))
    assert result.reason is StopReason.EXITED
    assert emu.register("EAX") == 100
    assert dword(emu, program.symbols["total"].address) == 100


# Cleaning: numbers, case, comments


@pytest.mark.parametrize("literal", ["10", "0Ah", "0x0A", "0ah", "1010b", "10d", "00010"])
def test_number_formats(literal):
    _, emu, _ = run(f"mov eax, {literal}\nret")
    assert emu.register("EAX") == 10


def test_character_constants():
    _, emu, _ = run("mov eax, 'A'\nmov ebx, \"AB\"\nret")
    assert (emu.register("EAX"), emu.register("EBX")) == (0x41, 0x4142)


def test_source_is_case_insensitive():
    _, emu, _ = run(".DATA\nTotal DD 7\n.CODE\nMAIN PROC\nMOV EAX, total\nRET\nmain ENDP\nEnd Main")
    assert emu.register("EAX") == 7


def test_strings_keep_case_and_semicolons():
    program = assemble('.data\nmsg db "Hi; there", 0\n.code\nret')
    assert program.data == b"Hi; there\x00"


# Data pass and symbol table


def test_symbol_table():
    program = assemble(
        ".data\na db 1, 2, 3\nb dw 5 dup(?)\nc sdword -1\nmsg db 'hey', 0\n.code\nret"
    )
    table = {n: (s.address, s.size, s.count, s.type_name) for n, s in program.symbols.items()}
    assert table == {
        "a": (DATA, 1, 3, "byte"),
        "b": (DATA + 3, 2, 5, "word"),
        "c": (DATA + 13, 4, 1, "sdword"),
        "msg": (DATA + 17, 1, 4, "byte"),
    }


def test_data_layout():
    program = assemble(
        ".data\nx dw 2 dup(3 dup(7)), 1\ny dd -2\nz db 'AB', 0Dh, 0Ah\np dd x\nq dd $\n.code\nret"
    )
    expected = (
        (7).to_bytes(2, "little") * 6
        + (1).to_bytes(2, "little")
        + (0xFFFF_FFFE).to_bytes(4, "little")
        + b"AB\r\n"
        + DATA.to_bytes(4, "little")
        + (DATA + 26).to_bytes(4, "little")
    )
    assert program.data == expected
    assert program.symbols["x"].count == 7


def test_constants_equ_and_redefinable_equals():
    program = assemble(
        ".data\narr dd 1, 2, 3\nn equ 4\nsize_bytes = $ - arr\nk = 1\nk = k + 1\n.code\nret"
    )
    assert program.constants == {"n": 4, "size_bytes": 12, "k": 2}


# Operand rewriting


@pytest.mark.parametrize(
    ("operand", "value"),
    [
        ("arr", 10),
        ("arr[4]", 20),
        ("[arr+8]", 30),
        ("arr+8", 30),
        ("arr[esi*4]", 20),
        ("dword ptr arr[esi]", 0x1400_0000),  # bytes 1..4 of the array
    ],
)
def test_memory_operands_with_variables(operand, value):
    _, emu, _ = run(f".data\narr dd 10, 20, 30\n.code\nmov esi, 1\nmov eax, {operand}\nret")
    assert emu.register("EAX") == value


def test_size_is_inferred_from_the_variable():
    program, emu, _ = run(".data\nb db 0FFh\nw dw 0FFFFh\n.code\ninc b\ninc w\nret")
    assert emu.read_memory(program.symbols["b"].address, 3) == b"\x00\x00\x00"


def test_offset_lengthof_sizeof_type():
    _, emu, _ = run(
        ".data\nfill db 0\narr dw 5 dup(0)\n.code\n"
        "mov eax, OFFSET arr\nmov ebx, LENGTHOF arr\nmov ecx, SIZEOF arr\nmov edx, TYPE arr\nret"
    )
    regs = [emu.register(r) for r in ("EAX", "EBX", "ECX", "EDX")]
    assert regs == [DATA + 1, 5, 10, 2]


def test_constants_in_code_and_signed_ptr():
    _, emu, _ = run(
        ".data\nv sdword -5\nlimit = 3\n.code\nmov ecx, limit * 2\nmov eax, sdword ptr v\nret"
    )
    assert (emu.register("ECX"), emu.register("EAX")) == (6, 0xFFFF_FFFB)


def test_location_counter_in_code():
    _, emu, result = run("nop\njmp $", max_steps=50)
    assert result.reason is StopReason.LIMIT
    assert emu.register("EIP") == CODE + 1


# Procedures, labels, entry point


def test_entry_point_from_end_directive():
    program = assemble(".code\nhelper PROC\nret\nhelper ENDP\nstart:\nnop\nret\nEND start")
    assert program.entry == program.labels["start"] == CODE + 1


def test_entry_point_defaults_to_main_then_first_label():
    assert assemble("nop\nfirst:\nret\nmain:\nret").entry == CODE + 2
    assert assemble("nop\nfirst:\nret").entry == CODE + 1
    assert assemble("nop\nret").entry == CODE


def test_procedures_and_calls():
    source = """
    .code
    main PROC
        mov eax, 3
        call square
        ret
    main ENDP
    square PROC
        imul eax, eax
        ret
    square ENDP
    END main
    """
    _, emu, _ = run(source)
    assert emu.register("EAX") == 9


# Line map


def test_line_map_counts_prefixed_instructions_once():
    source = "main:\n  cld\n  rep movsb\n  top: inc eax\n  lea esi, [esi]\n  ret"
    program = assemble(source)
    assert program.instruction_count == 5
    assert program.line_to_address == {2: CODE, 3: CODE + 1, 4: CODE + 3, 5: CODE + 4, 6: CODE + 6}
    assert program.address_to_line[CODE + 1] == 3
    assert program.labels == {"main": CODE, "top": CODE + 3}


def test_listing_shows_address_and_bytes():
    source = ".data\nx dd 1\n.code\nmov eax, x\nret"
    listing = assemble(source).listing(source).splitlines()
    assert "00500000" in listing[1] and "01 00 00 00" in listing[1]
    assert listing[3].split()[1:4] == ["00400000", "A1", "00"]


# Errors


def test_all_errors_are_reported_with_line_numbers():
    source = """.data
x dd 5
y db 300
.code
main proc
  mov eax, x
  foo eax
  mov al, x
  jmp nowhere
  ret
main endp
end main"""
    assert errors_of(source) == [
        (3, "value 300 does not fit in a byte"),
        (7, "unknown instruction 'foo'"),
        (8, "operand sizes do not match: al is 8 bits, the memory operand is 32 bits"),
        (9, "unknown name 'nowhere'"),
    ]


@pytest.mark.parametrize(
    ("source", "line", "text"),
    [
        ('.data\nmsg db "oops\n.code', 2, "missing its closing quote"),
        (".code\n.foo", 2, "unknown directive '.foo'"),
        (".code\nx dd 1", 2, "data definitions belong in the .data section"),
        (".data\nmov eax, 1", 2, "instructions belong in the .code section"),
        (".data\nx dd 1\nx dd 2", 3, "'x' is already defined on line 2"),
        (".data\neax dd 1", 2, "reserved word"),
        (".data\nstr dd 1", 2, "'str' is an instruction name"),
        (".code\nstr: ret", 2, "reserved word"),
        (".code\nmain proc\nret", 2, "procedure 'main' has no ENDP"),
        (".code\na proc\nret\nb endp", 4, "does not match an open PROC"),
        (".code\nmain proc uses eax\nret\nmain endp", 2, "PROC options 'uses eax'"),
        (".code\nmov ax, @data\nmov ds, ax", 2, "@data is a 16-bit segment value"),
        (".code\ninvoke ExitProcess, 0", 2, "INVOKE is not supported"),
        (".code\n.if eax == 1", 2, ".IF is not supported"),
        (".data\nbig dq 1", 2, "64-bit data (dq) is not supported"),
        (".code\njmp $+2", 2, "jumps to $+n"),
        (".code\nmov eax, zz", 2, "unknown name 'zz'"),
        (".data\nx dd 1 / 0", 2, "division by zero"),
        (".code\nret\nend nothere", 3, "END names 'nothere'"),
        ("INCLUDE other.inc", 1, "only Irvine32.inc is recognized"),
        (".data\ns db 'it''s'", 2, "doubled quotes"),
        (".code\nmain proc uses ebx\nret\nmain endp", 2, "save registers with PUSH and POP"),
    ],
)
def test_error_messages(source, line, text):
    assert any(n == line and text in message for n, message in errors_of(source))


def test_warnings_for_small_model_and_org():
    program = assemble(".model small\norg 100h\n.code\nret")
    assert [(w.line, w.text.split(" ")[0]) for w in program.warnings] == [
        (1, ".model"),
        (2, "ORG"),
    ]


def test_lines_after_end_are_ignored():
    assert assemble(".code\nmain:\nret\nend main\nthis is not code").instruction_count == 1


# Intel/NASM syntax mode


def test_intel_syntax_program():
    source = """
section .data
nums:   dd 3, 4, 5
count   equ ($ - nums) / 4
stars   times 4 db '*'
result  resd 1
section .text
global _start
_start:
    mov ecx, count
    mov esi, nums          ; a name is an address in this syntax
    xor eax, eax
again:
    add eax, [esi]
    add esi, 4
    loop again
    mov dword [result], eax
    mov bl, [stars]
    ret
"""
    program, emu, result = run(source, intel_syntax=True)
    assert result.reason is StopReason.EXITED
    assert emu.register("EAX") == 12
    assert emu.register("BL") == ord("*")
    assert dword(emu, program.symbols["result"].address) == 12
