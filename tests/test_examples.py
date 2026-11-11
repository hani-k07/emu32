"""Golden tests: every example runs to the end with its expected output."""

from pathlib import Path

import pytest

from emu32.emulator import StopReason
from emu32.gui.dialogs import looks_like_intel
from emu32.session import Session

EXAMPLES = Path(__file__).parent.parent / "src" / "emu32" / "examples"

# file -> (typed input, expected screen output)
EXPECTED = {
    "sum_array.asm": ("", "Sum: 100\n"),
    "factorial.asm": ("5\n", "Enter a number from 0 to 12: 5\nFactorial: 120\n"),
    "string_reverse.asm": ("", "desserts\n"),
    "bubble_sort.asm": ("", "1 3 7 19 25 42 88 \n"),
    "string_print.asm": ("", "Assembly is fun.\nFunction 09h prints up to the dollar sign.\n"),
    "simple_loop.asm": ("", "1 2 3 4 5 6 7 8 9 \n"),
    "fibonacci.asm": ("", "Fibonacci numbers:\n0 1 1 2 3 5 8 13 21 34 55 89 \n"),
    "find_max.asm": ("", "Highest: +27\n"),
}


def run_example(name: str, typed: str) -> tuple[Session, object]:
    source = (EXAMPLES / name).read_text(encoding="utf-8")
    session = Session()
    program = session.load(source, looks_like_intel(source))
    assert program.warnings == [], program.warnings
    session.console.feed(typed)
    return session, session.run()


def test_every_example_has_a_golden_test():
    assert sorted(p.name for p in EXAMPLES.glob("*.asm")) == sorted(EXPECTED)
    assert len(EXPECTED) >= 8


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_example_output(name):
    typed, expected = EXPECTED[name]
    session, outcome = run_example(name, typed)
    assert outcome.reason is StopReason.EXITED, outcome.message
    assert session.console.output() == expected


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("0\n", "Factorial: 1\n"),
        ("12\n", "Factorial: 479001600\n"),
        ("13\n", "Please enter"),
        ("-3\n", "Please enter"),
    ],
)
def test_factorial_edges(typed, expected):
    session, outcome = run_example("factorial.asm", typed)
    assert outcome.reason is StopReason.EXITED
    assert expected in session.console.output()


def test_examples_can_be_stepped_back_to_the_start():
    session, _ = run_example("bubble_sort.asm", "")
    session.reset()
    start = session.emulator.registers()
    for _ in range(50):
        session.step()
    while session.step_back():
        pass
    assert session.emulator.registers() == start
