"""Reading terminated strings out of emulator memory for the I/O services."""

from __future__ import annotations

from emu32.emulator import Emulator


class ServiceError(Exception):
    """A service could not do its job; becomes a run-time error at the calling line."""


def read_terminated(emu: Emulator, address: int, terminator: int, what: str) -> bytes:
    region = next((r for r in emu.mode.regions if r.contains(address)), None)
    where = emu.mode.format_address(address)
    if region is None:
        raise ServiceError(f"{what}: address {where} is outside the program's memory")
    blob = emu.read_memory(address, region.end - address)
    end = blob.find(terminator)
    if end < 0:
        mark = "'$'" if terminator == ord("$") else "0 byte"
        raise ServiceError(f"{what}: the string at {where} has no terminating {mark}")
    return blob[:end]
