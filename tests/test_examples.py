"""Golden tests: every example runs to the end with its expected output."""

from pathlib import Path

import pytest

from emu32.emulator import StopReason
from emu32.gui.dialogs import looks_like_intel
from emu32.session import Session

EXAMPLES = Path(__file__).parent.parent / "src" / "emu32" / "examples"

# file -> (typed input, expected screen output)
EXPECTED = {
    "com/hello_world.asm": ("", "Hello, world!\n"),
    "com/echo_key.asm": ("x", "Press a key: x\nYou pressed: x"),
    "com/sum_array.asm": ("", "Sum: 100"),
    "com/compare_branch.asm": ("", "The first number is bigger."),
    "com/counting_loop.asm": ("", "1 2 3 4 5 6 7 8 9 "),
    "com/string_reverse.asm": ("", "desserts"),
    "com/stack_parameters.asm": ("", "35"),
    "com/macro_print.asm": ("", "Macros save typing.\nThe assembler copies them in."),
    "com/buffered_input.asm": ("Sara\n", "Your name: Sara\nHello, Sara!"),
    "com/factorial.asm": (
        "",
        "1! = 1\n2! = 2\n3! = 6\n4! = 24\n5! = 120\n6! = 720\n7! = 5040\n8! = 40320\n",
    ),
    "com/bubble_sort.asm": ("", "1 2 3 5 7 9 "),
    "com/find_max.asm": ("", "Largest: 42"),
    "com/fibonacci.asm": ("", "0 1 1 2 3 5 8 13 21 34 55 89 "),
    "com/mixed_32bit.asm": ("", "1000 * 3000 = 3000000"),
    "exe/hello_world.asm": ("", "Hello from an EXE program!\n"),
    "exe/sum_array.asm": ("", "Sum: 1000"),
    "flat/sum_array.asm": ("", "Sum: 100\n"),
    "flat/factorial.asm": ("5\n", "Enter a number from 0 to 12: 5\nFactorial: 120\n"),
    "flat/string_reverse.asm": ("", "desserts\n"),
    "flat/bubble_sort.asm": ("", "1 3 7 19 25 42 88 \n"),
    "flat/string_print.asm": (
        "",
        "Assembly is fun.\nFunction 09h prints up to the dollar sign.\n",
    ),
    "flat/simple_loop.asm": ("", "1 2 3 4 5 6 7 8 9 \n"),
    "flat/fibonacci.asm": ("", "Fibonacci numbers:\n0 1 1 2 3 5 8 13 21 34 55 89 \n"),
    "flat/find_max.asm": ("", "Highest: +27\n"),
    "flat/grade_report.asm": (
        "",
        "91 -> A\n78 -> C\n85 -> B\n52 -> F\n67 -> D\n100 -> A\nPassed: 5 of 6\n",
    ),
    "flat/employee_records.asm": ("", "Total salary: 159000\nLongest service: Chen\n"),
    "flat/add_64bit.asm": ("", "Result: 0000000400000000h\n"),
}
MODEL_OF_GROUP = {"com": "com", "exe": "exe", "flat": "flat"}


def run_example(name: str, typed: str) -> tuple[Session, object]:
    source = (EXAMPLES / name).read_text(encoding="utf-8")
    session = Session()
    program = session.load(source, looks_like_intel(source))
    assert program.warnings == [], program.warnings
    session.console.feed(typed)
    return session, session.run()


def test_every_example_has_a_golden_test():
    found = sorted(p.relative_to(EXAMPLES).as_posix() for p in EXAMPLES.glob("*/*.asm"))
    assert found == sorted(EXPECTED)
    assert sum(name.startswith("com/") for name in EXPECTED) >= 14  # spec 12.2


def test_examples_have_a_description_and_level_and_match_their_folder():
    from emu32.gui.editor_window import examples

    found = examples()
    assert [e.group for e in found][:1] == ["com"]  # COM first
    for example in found:
        assert example.description and example.level in ("Basic", "Intermediate"), example
        program = Session().compile(
            example.path.read_text(encoding="utf-8"),
            looks_like_intel(example.path.read_text(encoding="utf-8")),
        )
        assert program.mode.key == MODEL_OF_GROUP[example.group], example.path


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
    session, outcome = run_example("flat/factorial.asm", typed)
    assert outcome.reason is StopReason.EXITED
    assert expected in session.console.output()


def test_examples_can_be_stepped_back_to_the_start():
    session, _ = run_example("com/bubble_sort.asm", "")
    session.reset()
    start = session.emulator.registers()
    for _ in range(50):
        session.step()
    while session.step_back():
        pass
    assert session.emulator.registers() == start
