"""Program models: the facts that differ between COM, EXE and flat 32-bit programs.

Everything else asks the ProgramModel for these values instead of assuming one layout.
COM and EXE programs run on the CPU in 16-bit real mode with all segments at 0: the CPU then
behaves like an 8086 for `call`, `ret`, `loop`, string instructions and stack frames, and
the 32-bit registers stay usable, as on a 386 (D81).
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
class ProgramModel:
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
    key: str = "flat"  # "com", "exe" or "flat"
    base_pointer: str = "EBP"
    # Registers read with every snapshot but not in the main list (the 32-bit registers of
    # a 16-bit model), so step back restores them and a "Show 32-bit" view can show them.
    extra_registers: tuple[str, ...] = ()
    # Where `ret` from the entry procedure goes; reaching it ends the program.
    return_address: int = 0x0030_0000
    # Bytes written at load: the exit stub (flat) or `int 20h` at offset 0 (COM, EXE).
    startup_bytes: tuple[tuple[int, bytes], ...] = ((0x0030_0000, b"\xf4"),)
    stack_top: int = 0x0080_0000
    image_base: int = 0x100  # COM: the ORG address; EXE: where .data starts

    @property
    def word_size(self) -> int:
        return self.bits // 8

    @property
    def label(self) -> str:
        return {"com": "COM", "exe": "EXE"}.get(self.key, "Flat 32-bit")

    @property
    def is_16bit(self) -> bool:
        return self.bits == 16

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


MODE32 = ProgramModel(
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
FLAT_MODEL = MODE32
CpuMode = ProgramModel  # the earlier name, still used across the code


def _sub_registers_16() -> dict[str, tuple[str, int, int]]:
    table = {}
    for letter in "ABCD":
        table[f"{letter}H"] = (f"{letter}X", 8, 8)
        table[f"{letter}L"] = (f"{letter}X", 0, 8)
    return table


def _model_16(key: str) -> ProgramModel:
    # One 64 KB segment at 0, as a DOS program sees it with every segment register 0.
    memory = Region("memory", 0, 0x1_0000, READ | WRITE | EXEC)
    return ProgramModel(
        name=key.upper(),
        bits=16,
        uc_mode=unicorn.UC_MODE_16,
        ks_mode=keystone.KS_MODE_16,
        cs_mode=capstone.CS_MODE_16,
        registers=(
            "AX",
            "BX",
            "CX",
            "DX",
            "SI",
            "DI",
            "BP",
            "SP",
            "IP",
            "FLAGS",
            "CS",
            "DS",
            "ES",
            "SS",
        ),  # fmt: skip
        instruction_pointer="IP",
        stack_pointer="SP",
        flags_register="FLAGS",
        initial_flags=0x202,
        sub_registers=_sub_registers_16(),
        regions=(memory,),
        key=key,
        base_pointer="BP",
        extra_registers=(
            "EAX",
            "EBX",
            "ECX",
            "EDX",
            "ESI",
            "EDI",
            "EBP",
            "ESP",
            "EIP",
            "EFLAGS",
        ),  # fmt: skip
        # A COM program's stack starts with a 0 word, so `ret` jumps to offset 0, where
        # DOS puts `int 20h` (the start of the PSP).
        return_address=0,
        startup_bytes=((0, b"\xcd\x20"),),
        stack_top=0x1_0000,
    )


COM_MODEL = _model_16("com")
EXE_MODEL = _model_16("exe")
MODELS = {"com": COM_MODEL, "exe": EXE_MODEL, "flat": FLAT_MODEL}
