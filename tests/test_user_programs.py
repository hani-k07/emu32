"""Programs sent in by users, kept as regression tests."""

from pathlib import Path

from emu32.emulator import StopReason
from emu32.session import Session

PROGRAMS = Path(__file__).parent / "user_programs"


def test_stress_test_runs_to_the_end():
    """50 million instructions of busy-wait loops, int 21h output and input."""
    session = Session()
    session.load((PROGRAMS / "stress_test.asm").read_text(encoding="utf-8"))
    session.console.feed("x")
    outcome = session.run()
    assert outcome.reason is StopReason.EXITED, outcome.message
    output = session.console.output()
    for expected in (
        "(125000 * 4 + 54321): 554321",
        "Original Array: 4500 12 98765 340 1024 5 77777 89 ",
        "Sorted Array:   5 12 89 340 1024 4500 77777 98765 ",
        "Reversed Text:  !skroW ledoM yromeM talF tiB-23",
        "Shutting down in: 5 4 3 2 1 ",
        "All 32-bit tests passed! Goodbye.",
    ):
        assert expected in output
