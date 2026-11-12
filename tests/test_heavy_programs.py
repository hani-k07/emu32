"""Heavier programs, one per algorithm family, each with an expected output that was
computed independently in Python (see the .exp files next to the programs)."""

from pathlib import Path

import pytest

from emu32.emulator import StopReason
from emu32.session import Session

PROGRAMS = Path(__file__).parent / "heavy_programs"


@pytest.mark.parametrize("path", sorted(PROGRAMS.glob("*.asm")), ids=lambda p: p.stem)
def test_heavy_program_output(path):
    session = Session()
    session.load(path.read_text(encoding="utf-8"))
    outcome = session.run()
    assert outcome.reason is StopReason.EXITED, outcome.message
    assert session.console.output() == path.with_suffix(".exp").read_text(encoding="utf-8")
