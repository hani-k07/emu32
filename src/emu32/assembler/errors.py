from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AsmMessage:
    line: int
    text: str

    def __str__(self) -> str:
        return f"line {self.line}: {self.text}"


class AsmError(Exception):
    """One problem on one line, raised inside a pass and collected by the caller."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.text = text


class AssemblyError(Exception):
    """Assembly failed; `errors` lists every problem found, in line order."""

    def __init__(self, errors: list[AsmMessage]) -> None:
        self.errors = sorted(errors, key=lambda e: e.line)
        super().__init__("\n".join(str(e) for e in self.errors))
