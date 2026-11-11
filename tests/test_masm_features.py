"""MASM features used in Visual Studio courses: macros, decision directives, STRUCT, QWORD,
LABEL, ALIGN, TEXTEQU and @@ labels. tests/vs_programs holds whole course-style programs."""

from pathlib import Path

import pytest

from emu32.assembler import AssemblyError
from emu32.emulator import StopReason
from emu32.session import Session

PROGRAMS = Path(__file__).parent / "vs_programs"

EXPECTED = {
    "p01_irvine_basics.asm": "Sum = 00060000\nSizes: 8 3 2\n+2\n",
    "p02_vs_template.asm": "",
    "p03_procs.asm": "720\n25\n6\n",
    "p04_strings.asm": "Assembly is fun\n**********\nfun\nequal\nName: Kareem\nHello, Kareem\n15\n",
    "p05_highlevel.asm": "between\n15\n64\nnegative\n",
    "p06_macros.asm": "42\n7\n9\n12\n",
    "p07_struct.asm": "Salary: 45000\n5\n9\n45\n103\n",
    "p09_arrays.asm": "10\n40\n3\n12\n",
    "p10_labels.asm": "12345678\n321\njumped\nglobal\n",
    "q01_invoke.asm": "35\n",
    "q02_multiword.asm": "0000000122C32B0674BB5736\n-1\n3456789A\n00000083\n15 19 -1\n4\n",
    "q03_strings_lib.asm": "HELLO WORLD\nsame\n11\n+4\n",
    "q04_locals.asm": "0 1 1 2 3 5 8 13 21 34 \nedcba\n12\n",
}


def run(source: str, feed: str = "") -> str:
    session = Session()
    session.load(source)
    session.console.feed(feed)
    outcome = session.run()
    assert outcome.reason is StopReason.EXITED, outcome.message
    return session.console.output().replace("\r\n", "\n")


def errors(source: str) -> list[tuple[int, str]]:
    with pytest.raises(AssemblyError) as caught:
        Session().load(source)
    return [(e.line, e.text) for e in caught.value.errors]


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_course_programs(name):
    output = run((PROGRAMS / name).read_text(encoding="utf-8"), "Kareem\n")
    assert output == EXPECTED[name]


def test_arithmetic_program():
    output = run((PROGRAMS / "p08_arith.asm").read_text(encoding="utf-8"))
    assert output.startswith("-14-2\n34567812\n-100\n-4\n45\n90ABCDEF12345678\n1\ndone\n")


def program(body: str, data: str = "") -> str:
    return (
        f"INCLUDE Irvine32.inc\n.data\n{data}\n.code\nmain PROC\n{body}\n"
        "exit\nmain ENDP\nEND main\n"
    )


def test_nested_loops_with_break_and_continue():
    body = """
    mov ecx, 0
    .WHILE 1
        inc ecx
        .CONTINUE .IF ecx == 2
        .BREAK .IF ecx > 4
        mov eax, ecx
        call WriteDec
    .ENDW
    """
    assert run(program(body)) == "134"


def test_or_not_and_flag_conditions():
    body = """
    mov eax, 3
    .IF eax == 1 || eax == 3
        mWrite "a"
    .ENDIF
    .IF !(eax == 3)
        mWrite "b"
    .ELSE
        mWrite "c"
    .ENDIF
    stc
    .IF CARRY?
        mWrite "d"
    .ENDIF
    mov ebx, 0
    .IF ebx
        mWrite "e"
    .ENDIF
    """
    assert run(program(body)) == "acd"


def test_signed_variables_use_signed_jumps():
    body = """
    .IF small < 1
        mWrite "signed"
    .ENDIF
    mov eax, -1
    .IF eax > 1
        mWrite " unsigned"
    .ENDIF
    """
    assert run(program(body, "small SDWORD -3")) == "signed unsigned"


def test_repeat_untilcxz():
    body = """
    mov ecx, 3
    .REPEAT
        mWrite "x"
    .UNTILCXZ
    """
    assert run(program(body)) == "xxx"


def test_macro_defaults_required_and_textequ():
    source = """INCLUDE Irvine32.inc
INCLUDE Macros.inc
greeting TEXTEQU <"hi">
mShow MACRO value:REQ, times:=<2>
    LOCAL again
    mov ecx, times
again:
    mWrite value
    loop again
ENDM
.code
main PROC
    mShow greeting
    mShow "-", 3
    mWriteSpace
    mWriteLn "end"
    exit
main ENDP
END main
"""
    assert run(source) == "hihi--- end\n"


def test_struct_arrays_and_operators():
    source = """INCLUDE Irvine32.inc
Point STRUCT
    x DWORD 0
    y DWORD 0
Point ENDS
.data
points Point 3 DUP(<1, 2>)
.code
main PROC
    mov eax, LENGTHOF points
    call WriteDec
    mov eax, TYPE points
    call WriteDec
    mov eax, SIZEOF points
    call WriteDec
    mov esi, OFFSET points
    add esi, TYPE Point
    mov (Point PTR [esi]).y, 7
    mov eax, points.y + 8
    call WriteDec
    mov eax, Point.y
    call WriteDec
    exit
main ENDP
END main
"""
    assert run(source) == "3824" + "74"


def test_qword_label_and_align():
    source = """INCLUDE Irvine32.inc
.data
b BYTE 1
ALIGN 4
both LABEL QWORD
lo DWORD 5
hi DWORD 6
.code
main PROC
    mov eax, OFFSET lo
    and eax, 3
    call WriteDec
    mov eax, DWORD PTR both + 4
    call WriteDec
    exit
main ENDP
END main
"""
    assert run(source) == "06"


@pytest.mark.parametrize(
    ("source", "line", "text"),
    [
        (".code\n.endif", 2, ".ENDIF without a matching .IF"),
        (".code\n.while eax < 3", 2, "this block has no .ENDW"),
        (".code\n.break", 2, ".BREAK belongs inside .WHILE or .REPEAT"),
        (".code\n.if\n.endif", 2, "a condition is missing"),
        ("m MACRO\nnop", 1, "macro 'm' has no ENDM"),
        ("m MACRO a:REQ\nnop\nENDM\n.code\nm", 5, "needs a value for 'a'"),
        ("m MACRO\nm\nENDM\n.code\nm", 5, "calls itself too deeply"),
        ("m MACRO a\nENDM\n.code\nm 1, 2", 4, "takes 1 arguments, not 2"),
        (".code\njmp @f", 2, "@F has no @@: label"),
        ("P STRUCT\nx DWORD 0", 1, "STRUCT 'p' has no ENDS"),
        ("P STRUCT\nx DWORD 0\nP ENDS\n.data\nv P <1, 2>", 5, "p has 1 fields"),
        ("P STRUCT\nx BYTE 'ab'\nP ENDS\n.data\nv P <'abc'>", 5, "too long for the field"),
        ("P STRUCT\nx DWORD 0\nP ENDS\n.data\nv P <>\n.code\nmov eax, v.z", 7, "no field 'z'"),
    ],
)
def test_error_messages(source, line, text):
    found = errors(source)
    assert any(n == line and text in message for n, message in found), found


def test_fpu_program():
    output = run((PROGRAMS / "q05_fpu.asm").read_text(encoding="utf-8"), "1.5\n")
    assert output == (
        "+1.9634954E+001\n20\n+3.0000000E+000\nsum > 0.5\n+1.0000000E+005\n"
        "Enter a number: 1.5\n+2.2500000E+000\n"
        "ST(0): +2.2500000E+000\nST(1): +1.0000000E+005\n"
    )


def test_read_float_rejects_text_with_overflow_flag():
    body = 'call ReadFloat\njno ok\nmWrite "bad "\nok: call WriteFloat'
    assert run(program(body), "abc\n").endswith("bad +0.0000000E+000")


def test_write_float_on_an_empty_stack_is_a_friendly_error():
    session = Session()
    session.load(program("call WriteFloat"))
    outcome = session.run()
    assert outcome.reason is StopReason.ERROR
    assert "FPU stack is empty" in outcome.message


def test_step_back_restores_the_fpu_stack():
    session = Session()
    session.load(program("fld1\nfldpi", "x REAL8 2.0"))
    session.step()
    session.step()
    assert session.emulator.fpu_stack()[:2] == [pytest.approx(3.14159265), 1.0]
    session.step_back()
    assert session.emulator.fpu_stack()[:2] == [1.0, None]


@pytest.mark.parametrize("value", [0.0, 1.0, -2.5, 1e10, 3.141592653589793, -1e-300])
def test_real10_round_trip(value):
    from emu32.assembler.data_pass import pack_real
    from emu32.emulator.core import extended_to_float

    raw = pack_real(value, 10)
    mantissa, exponent = int.from_bytes(raw[:8], "little"), int.from_bytes(raw[8:], "little")
    assert extended_to_float(mantissa, exponent) == value


def test_real_data_and_float_literal_errors():
    session = Session()
    program_ = session.load(program("nop", "a REAL4 1.5\nb REAL8 -2.0E+3\nc REAL10 ?"))
    assert [program_.symbols[n].size for n in "abc"] == [4, 8, 10]
    assert errors(program("nop", "d DWORD 1.5")) == [
        (3, "1.5 is a floating-point number; declare it as REAL4 or REAL8")
    ]


def test_conditional_assembly_and_repeat_blocks():
    output = run((PROGRAMS / "q06_conditional.asm").read_text(encoding="utf-8"))
    assert output == "1 4 9 16 25 \nabc\n8\n0 0\ndebug build\nfive\n"


@pytest.mark.parametrize(
    ("source", "line", "text"),
    [
        (".code\nendif", 2, "ENDIF without a matching IF"),
        (".code\nif 1", 2, "IF has no ENDIF"),
        (".code\nrept 3\nnop", 2, "REPT has no ENDM"),
        (".data\nx dword 1\n.code\nif x\nendif", 4, "needs a constant expression"),
        ("n = 1\nwhile n\nendm", 2, "WHILE repeated 10000 times"),
        (".code\nifidn <a>\nendif", 2, "IFIDN compares two texts"),
        (".code\nfor x\nendm", 2, "write FOR name, <items>"),
    ],
)
def test_conditional_errors(source, line, text):
    found = errors(source)
    assert any(n == line and text in message for n, message in found), found
