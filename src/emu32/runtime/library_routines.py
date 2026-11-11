"""Console library routines, written for emu32.

Each routine has a one-byte stub (`ret`) in the library-stub region. A `call WriteString`
lands on the stub; a code hook limited to that region runs the Python routine, then the real
`ret` returns to the caller. If the routine stops the program (exit, error, cancelled input)
the `ret` does not run.

Register use:
    WriteString  EDX = address of a 0-terminated string
    WriteChar    AL  = character
    WriteInt     EAX, signed decimal with a leading sign (+5, -5)
    WriteDec     EAX, unsigned decimal
    WriteHex     EAX, eight hex digits
    Crlf         new line
    ReadInt      reads a line into EAX; OF=1 and EAX=0 if it is not a 32-bit integer
    ReadChar     reads one character into AL, without echo; Enter gives 0Dh
    ReadString   EDX = buffer, ECX = buffer size; stores at most ECX-1 characters and a 0;
                 EAX = number of characters stored
    DumpRegs     prints the registers and flags as the caller sees them
    exit         ends the program (exit code 0)
    ExitProcess  ends the program; exit code is the dword argument on the stack
"""

from __future__ import annotations

from collections.abc import Callable

import unicorn

from emu32.cpu_mode import CpuMode
from emu32.emulator import Emulator, EmulatorError, HookStop
from emu32.emulator.flags import FLAG_BITS
from emu32.runtime.console import ENCODING, Console, InputCancelled
from emu32.runtime.memory_text import ServiceError, read_terminated

RET = b"\xc3"
STUB_SPACING = 16

Routine = Callable[[Emulator, Console], None]


def _signed(value: int) -> int:
    return value - (1 << 32) if value & 0x8000_0000 else value


def _write_string(emu: Emulator, con: Console) -> None:
    con.write_bytes(read_terminated(emu, emu.register("EDX"), 0, "WriteString"))


def _write_char(emu: Emulator, con: Console) -> None:
    con.write_bytes(bytes([emu.register("AL")]))


def _write_int(emu: Emulator, con: Console) -> None:
    con.write(f"{_signed(emu.register('EAX')):+d}")


def _write_dec(emu: Emulator, con: Console) -> None:
    con.write(str(emu.register("EAX")))


def _write_hex(emu: Emulator, con: Console) -> None:
    con.write(f"{emu.register('EAX'):08X}")


def _crlf(emu: Emulator, con: Console) -> None:
    con.write("\n")


def _set_overflow(emu: Emulator, value: bool) -> None:
    flags = emu.register("EFLAGS")
    bit = 1 << FLAG_BITS["OF"]
    emu.set_register("EFLAGS", flags | bit if value else flags & ~bit)


def _read_int(emu: Emulator, con: Console) -> None:
    line = con.read_line()
    con.write(line + "\n")
    try:
        value = int(line.strip(), 10)
        valid = -(1 << 31) <= value < (1 << 31)
    except ValueError:
        valid = False
    emu.set_register("EAX", value if valid else 0)
    _set_overflow(emu, not valid)


def _read_char(emu: Emulator, con: Console) -> None:
    char = con.read_char()
    emu.set_register("AL", 0x0D if char == "\n" else char.encode(ENCODING, "replace")[0])


def _read_string(emu: Emulator, con: Console) -> None:
    line = con.read_line()
    con.write(line + "\n")
    room = max(emu.register("ECX") - 1, 0)
    text = line.encode(ENCODING, "replace")[:room]
    buffer = emu.register("EDX")
    try:
        emu.write_memory(buffer, text + b"\x00")
    except EmulatorError as error:
        where = emu.mode.format_address(buffer)
        raise ServiceError(f"ReadString: cannot write the buffer at {where}") from error
    emu.set_register("EAX", len(text))


def _dump_regs(emu: Emulator, con: Console) -> None:
    regs = emu.registers()
    # The caller's view: before the call pushed the return address.
    return_address = int.from_bytes(emu.read_memory(regs["ESP"], 4), "little")
    regs["ESP"] += 4
    regs["EIP"] = return_address
    flags = " ".join(f"{name}={value}" for name, value in emu.flags().items())
    con.write(
        "\n"
        f"EAX={regs['EAX']:08X}  EBX={regs['EBX']:08X}  ECX={regs['ECX']:08X}  "
        f"EDX={regs['EDX']:08X}\n"
        f"ESI={regs['ESI']:08X}  EDI={regs['EDI']:08X}  EBP={regs['EBP']:08X}  "
        f"ESP={regs['ESP']:08X}\n"
        f"EIP={regs['EIP']:08X}  EFL={regs['EFLAGS']:08X}  {flags}\n\n"
    )


def _exit(emu: Emulator, con: Console) -> None:
    emu.exit_program(0)


def _exit_process(emu: Emulator, con: Console) -> None:
    code = int.from_bytes(emu.read_memory(emu.register("ESP") + 4, 4), "little")
    emu.exit_program(code)


# Order fixes each stub's address; append new routines at the end.
ROUTINES: dict[str, Routine] = {
    "writestring": _write_string,
    "writechar": _write_char,
    "writeint": _write_int,
    "writedec": _write_dec,
    "writehex": _write_hex,
    "crlf": _crlf,
    "readint": _read_int,
    "readchar": _read_char,
    "readstring": _read_string,
    "dumpregs": _dump_regs,
    "exit": _exit,
    "exitprocess": _exit_process,
}


# How the names are usually written, for display.
DISPLAY_NAMES = {
    "writestring": "WriteString", "writechar": "WriteChar", "writeint": "WriteInt",
    "writedec": "WriteDec", "writehex": "WriteHex", "crlf": "Crlf", "readint": "ReadInt",
    "readchar": "ReadChar", "readstring": "ReadString", "dumpregs": "DumpRegs",
    "exit": "exit", "exitprocess": "ExitProcess",
}  # fmt: skip


def routine_addresses(mode: CpuMode) -> dict[str, int]:
    """Stub address of each routine, keyed by lowercase name, for the assembler."""
    base = mode.region("library_stubs").start
    return {name: base + index * STUB_SPACING for index, name in enumerate(ROUTINES)}


def install(emu: Emulator, console: Console) -> None:
    """Write the stubs and hook them. Runs after every load."""
    handlers = {address: ROUTINES[name] for name, address in routine_addresses(emu.mode).items()}
    for address in handlers:
        emu.write_memory(address, RET)

    def on_stub(uc: unicorn.Uc, address: int, size: int, _data: object) -> None:
        routine = handlers.get(address)
        if routine is None:
            return
        try:
            routine(emu, console)
        except InputCancelled:
            raise HookStop from None
        except ServiceError as error:
            # Point at the call instruction: the byte before the return address.
            return_address = int.from_bytes(emu.read_memory(emu.register("ESP"), 4), "little")
            emu.fail(str(error), return_address - 1)

    region = emu.mode.region("library_stubs")
    emu.uc.hook_add(unicorn.UC_HOOK_CODE, on_stub, begin=region.start, end=region.end - 1)
