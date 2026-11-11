"""Programs for the course's lab topics 9 to 12, written for emu32, with their full output."""

from pathlib import Path

import pytest

from emu32.emulator import StopReason
from emu32.session import Session

TOPICS = Path(__file__).parent / "course_topics"

EXPECTED = {
    "lab09_shift_mul_div.asm": ("", "130\n0000 1111\n0000001234567800\n-7 -1\n10000000\n"),
    "lab10_library_extended_bcd.asm": (
        "2A\n",
        "000000000000000400000000\n83\n13\nEnter a hex number: 2A\n42\n"
        "0000 0000 0000 0000 0000 0000 0010 1010\n",
    ),
    "lab11_strings_arrays.asm": ("", "40\n5\n5\n8\nASSEMBLY\n26\n"),
    "lab12_procedures.asm": ("", "18\n42\n120\n1 4 9 \n3\n"),
}


def test_every_topic_program_has_expected_output():
    assert sorted(p.name for p in TOPICS.glob("*.asm")) == sorted(EXPECTED)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_topic_program(name):
    typed, expected = EXPECTED[name]
    session = Session()
    program = session.load((TOPICS / name).read_text(encoding="utf-8"))
    assert program.warnings == []
    session.console.feed(typed)
    outcome = session.run()
    assert outcome.reason is StopReason.EXITED, outcome.message
    assert session.console.output() == expected


def test_procedure_frames_step_back_cleanly():
    """Generated prologues and epilogues map to source lines and can be stepped back."""
    session = Session()
    program = session.load((TOPICS / "lab12_procedures.asm").read_text(encoding="utf-8"))
    start = session.emulator.registers()
    lines = set()
    for _ in range(60):
        outcome = session.step()
        lines.add(outcome.line)
    assert None not in lines  # every step stops on a source line
    while session.step_back():
        pass
    assert session.emulator.registers() == start
    # The INVOKE line maps to its first push; the PROC line to its prologue.
    assert program.line_to_address[13] == program.entry


def test_nasm_mode_does_not_change_later_masm_programs():
    """Keystone keeps hex as its default number base after NASM mode; generated code must
    not depend on it (D62)."""
    source = (TOPICS / "lab12_procedures.asm").read_text(encoding="utf-8")
    before = Session().load(source).code
    Session().load("section .text\n_start:\nmov eax, 12\nret", intel_syntax=True)
    assert Session().load(source).code == before
