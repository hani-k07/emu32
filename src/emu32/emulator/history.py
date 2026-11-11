"""Undo log for single steps: register snapshots plus the old bytes of every memory write."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from emu32.emulator.core import Emulator, MemoryAccess

DEFAULT_LIMIT = 10_000


@dataclass(frozen=True)
class HistoryEntry:
    registers: dict[str, int]
    writes: tuple[MemoryAccess, ...]
    total_steps: int
    exited: bool
    console_length: int


class History:
    def __init__(self, limit: int = DEFAULT_LIMIT) -> None:
        self._entries: deque[HistoryEntry] = deque(maxlen=limit)

    def __len__(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        self._entries.clear()

    def push(self, entry: HistoryEntry) -> None:
        self._entries.append(entry)

    def pop(self) -> HistoryEntry | None:
        return self._entries.pop() if self._entries else None


def undo(emu: Emulator, entry: HistoryEntry) -> None:
    # Newest write first, so overlapping writes end with the oldest bytes.
    for access in reversed(entry.writes):
        emu.uc.mem_write(access.address, access.old)
    for name, value in entry.registers.items():
        emu.set_register(name, value)
    emu.total_steps = entry.total_steps
    emu.exited = entry.exited
