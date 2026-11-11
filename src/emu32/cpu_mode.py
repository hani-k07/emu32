"""Facts that differ between CPU modes.

Everything else asks a CpuMode for these values instead of assuming 32 bits, so a 16-bit mode
can be added later by defining a second instance.
"""

from __future__ import annotations

from dataclasses import dataclass

import capstone
import keystone
import unicorn

READ = unicorn.UC_PROT_READ
WRITE = unicorn.UC_PROT_WRITE
EXEC = unicorn.UC_PROT_EXEC


@dataclass(frozen=True)
class Region:
    name: str
    start: int
    size: int
    perms: int

    @property
    def end(self) -> int:
        return self.start + self.size

    def contains(self, address: int) -> bool:
        return self.start <= address < self.end


@dataclass(frozen=True)
class CpuMode:
    name: str
    bits: int
    uc_mode: int
    ks_mode: int
    cs_mode: int
    # Main registers in display order. Names match Unicorn's UC_X86_REG_* constants.
    registers: tuple[str, ...]
    instruction_pointer: str
    stack_pointer: str
    flags_register: str
    initial_flags: int
    # Partial registers shown next to the main ones: name -> (parent, shift, width in bits).
    sub_registers: dict[str, tuple[str, int, int]]
    regions: tuple[Region, ...]

    @property
    def word_size(self) -> int:
        return self.bits // 8

    def region(self, name: str) -> Region:
        for region in self.regions:
            if region.name == name:
                return region
        raise KeyError(name)

    def format_address(self, address: int) -> str:
        return f"{address:0{self.bits // 4}X}"

    def split_registers(self, values: dict[str, int]) -> dict[str, int]:
        """Partial register values derived from a snapshot of the main registers."""
        return {
            name: (values[parent] >> shift) & ((1 << width) - 1)
            for name, (parent, shift, width) in self.sub_registers.items()
        }


def _sub_registers_32() -> dict[str, tuple[str, int, int]]:
    table = {}
    for letter in "ABCD":
        table[f"{letter}X"] = (f"E{letter}X", 0, 16)
        table[f"{letter}H"] = (f"E{letter}X", 8, 8)
        table[f"{letter}L"] = (f"E{letter}X", 0, 8)
    for name in ("SI", "DI", "BP", "SP"):
        table[name] = (f"E{name}", 0, 16)
    return table


MODE32 = CpuMode(
    name="32-bit",
    bits=32,
    uc_mode=unicorn.UC_MODE_32,
    ks_mode=keystone.KS_MODE_32,
    cs_mode=capstone.CS_MODE_32,
    registers=("EAX", "EBX", "ECX", "EDX", "ESI", "EDI", "EBP", "ESP", "EIP", "EFLAGS"),
    instruction_pointer="EIP",
    stack_pointer="ESP",
    flags_register="EFLAGS",
    # Bit 1 is reserved and always set; IF on matches a normal user program.
    initial_flags=0x202,
    sub_registers=_sub_registers_32(),
    regions=(
        Region("exit_stub", 0x0030_0000, 0x1000, READ | EXEC),
        Region("library_stubs", 0x0031_0000, 0x1000, READ | EXEC),
        Region("code", 0x0040_0000, 0x1_0000, READ | EXEC),
        Region("data", 0x0050_0000, 0x1_0000, READ | WRITE),
        Region("stack", 0x0070_0000, 0x10_0000, READ | WRITE),
    ),
)
