"""Console library routines, written for emu32.

Each routine has a stub (`ret`, or `ret n`) in the library-stub region. A `call WriteString`
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

More routines (WriteBin, ReadDec, DumpMem, Random32, the Str_ procedures and others) are
listed with their register use in help/syntax.md. The Str_ procedures take dword arguments
on the stack (INVOKE) and remove them on return, so their stubs are `ret n`.
"""

from __future__ import annotations

import datetime
import random
import time
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


def _arg(emu: Emulator, index: int) -> int:
    """A dword argument pushed by the caller (INVOKE or push/call)."""
    return int.from_bytes(emu.read_memory(emu.register("ESP") + 4 + 4 * index, 4), "little")


def _set_flags(emu: Emulator, **values: bool) -> None:
    flags = emu.register("EFLAGS")
    for name, value in values.items():
        bit = 1 << FLAG_BITS[name]
        flags = flags | bit if value else flags & ~bit
    emu.set_register("EFLAGS", flags)


def _grouped_binary(value: int, bits: int) -> str:
    digits = f"{value & ((1 << bits) - 1):0{bits}b}"
    return " ".join(digits[i : i + 4] for i in range(0, bits, 4))


def _unit_size(emu: Emulator) -> int:
    size = emu.register("EBX")
    return size if size in (1, 2, 4) else 4


def _write_bin(emu: Emulator, con: Console) -> None:
    con.write(_grouped_binary(emu.register("EAX"), 32))


def _write_bin_b(emu: Emulator, con: Console) -> None:
    con.write(_grouped_binary(emu.register("EAX"), 8 * _unit_size(emu)))


def _write_hex_b(emu: Emulator, con: Console) -> None:
    size = _unit_size(emu)
    con.write(f"{emu.register('EAX') & ((1 << 8 * size) - 1):0{2 * size}X}")


def _read_dec(emu: Emulator, con: Console) -> None:
    line = con.read_line()
    con.write(line + "\n")
    text = line.strip()
    valid = text.isdigit() and int(text) < (1 << 32)
    emu.set_register("EAX", int(text) if valid else 0)
    _set_flags(emu, CF=not valid)


def _read_hex(emu: Emulator, con: Console) -> None:
    line = con.read_line()
    con.write(line + "\n")
    text = line.strip().removesuffix("h").removesuffix("H")
    try:
        value = int(text, 16) if 0 < len(text) <= 8 else -1
    except ValueError:
        value = -1
    emu.set_register("EAX", max(value, 0))
    _set_flags(emu, CF=value < 0)


def _string(emu: Emulator, address: int, what: str) -> bytes:
    return read_terminated(emu, address, 0, what)


def _store(emu: Emulator, address: int, data: bytes, what: str) -> None:
    try:
        emu.write_memory(address, data)
    except EmulatorError as error:
        where = emu.mode.format_address(address)
        raise ServiceError(f"{what}: cannot write at {where}") from error


def _str_length(emu: Emulator, con: Console) -> None:
    emu.set_register("EAX", len(_string(emu, _arg(emu, 0), "Str_length")))


def _str_copy(emu: Emulator, con: Console) -> None:
    source, target = _arg(emu, 0), _arg(emu, 1)
    _store(emu, target, _string(emu, source, "Str_copy") + b"\x00", "Str_copy")


def _str_compare(emu: Emulator, con: Console) -> None:
    """Sets the flags as CMP would on the first pair of bytes that differ."""
    first = _string(emu, _arg(emu, 0), "Str_compare") + b"\x00"
    second = _string(emu, _arg(emu, 1), "Str_compare") + b"\x00"
    a, b = next(((x, y) for x, y in zip(first, second, strict=False) if x != y), (0, 0))
    difference = (a - b) & 0xFF
    signed_a, signed_b = a - 256 * (a > 127), b - 256 * (b > 127)
    _set_flags(
        emu,
        ZF=a == b,
        CF=a < b,
        SF=bool(difference & 0x80),
        OF=not -128 <= signed_a - signed_b <= 127,
    )


def _str_ucase(emu: Emulator, con: Console) -> None:
    address = _arg(emu, 0)
    text = _string(emu, address, "Str_ucase")
    _store(emu, address, bytes(c - 32 if 97 <= c <= 122 else c for c in text), "Str_ucase")


def _str_trim(emu: Emulator, con: Console) -> None:
    """Removes trailing copies of the character passed as the second argument."""
    address, char = _arg(emu, 0), _arg(emu, 1) & 0xFF
    text = _string(emu, address, "Str_trim")
    _store(emu, address, text.rstrip(bytes([char])) + b"\x00", "Str_trim")


def _dump_mem(emu: Emulator, con: Console) -> None:
    start, count, size = emu.register("ESI"), emu.register("ECX"), _unit_size(emu)
    data = emu.read_memory(start, count * size) if count else b""
    values = [int.from_bytes(data[i : i + size], "little") for i in range(0, len(data), size)]
    lines = [
        "  ".join(f"{v:0{2 * size}X}" for v in values[i : i + 8]) for i in range(0, len(values), 8)
    ]
    con.write(f"\nMemory at {start:08X}, {count} x {size} bytes:\n" + "\n".join(lines) + "\n")


def _rng(emu: Emulator) -> random.Random:
    # Fixed seed until Randomize, so a program gives the same numbers every run.
    return emu.__dict__.setdefault("_rng", random.Random(1))


def _randomize(emu: Emulator, con: Console) -> None:
    _rng(emu).seed(time.time_ns())


def _random32(emu: Emulator, con: Console) -> None:
    emu.set_register("EAX", _rng(emu).getrandbits(32))


def _random_range(emu: Emulator, con: Console) -> None:
    limit = emu.register("EAX")
    emu.set_register("EAX", _rng(emu).randrange(limit) if limit else 0)


def _delay(emu: Emulator, con: Console) -> None:
    end = time.monotonic() + min(emu.register("EAX"), 60_000) / 1000
    while time.monotonic() < end:
        if emu._stop_requested:  # Stop ends a long delay early
            raise HookStop
        time.sleep(min(0.02, max(end - time.monotonic(), 0)))


def _clrscr(emu: Emulator, con: Console) -> None:
    con.clear_output()


def _ignore(emu: Emulator, con: Console) -> None:
    """Text color and cursor position have no meaning in the plain-text Screen window."""


def _wait_msg(emu: Emulator, con: Console) -> None:
    con.write("Press Enter to continue...")
    con.read_line()
    con.write("\n")


def _is_digit(emu: Emulator, con: Console) -> None:
    _set_flags(emu, ZF=0x30 <= emu.register("AL") <= 0x39)


def _get_mseconds(emu: Emulator, con: Console) -> None:
    now = datetime.datetime.now()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    emu.set_register("EAX", int((now - midnight).total_seconds() * 1000))


def _read_key(emu: Emulator, con: Console) -> None:
    char = con.try_read_char()
    if char is None:
        _set_flags(emu, ZF=True)
        return
    emu.set_register("EAX", 0x0D if char == "\n" else char.encode(ENCODING, "replace")[0])
    _set_flags(emu, ZF=False)


def _buffer_text(emu: Emulator, what: str) -> str:
    data = emu.read_memory(emu.register("EDX"), emu.register("ECX"))
    return data.split(b"\x00")[0].decode(ENCODING).strip()


def _parse_decimal32(emu: Emulator, con: Console) -> None:
    text = _buffer_text(emu, "ParseDecimal32")
    valid = text.isdigit() and int(text) < (1 << 32)
    emu.set_register("EAX", int(text) if valid else 0)
    _set_flags(emu, CF=not valid)


def _parse_integer32(emu: Emulator, con: Console) -> None:
    text = _buffer_text(emu, "ParseInteger32")
    try:
        value = int(text, 10)
        valid = -(1 << 31) <= value < (1 << 31)
    except ValueError:
        valid = False
    emu.set_register("EAX", value if valid else 0)
    _set_flags(emu, OF=not valid)


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
    "writebin": _write_bin,
    "writebinb": _write_bin_b,
    "writehexb": _write_hex_b,
    "readdec": _read_dec,
    "readhex": _read_hex,
    "str_length": _str_length,
    "str_copy": _str_copy,
    "str_compare": _str_compare,
    "str_ucase": _str_ucase,
    "str_trim": _str_trim,
    "dumpmem": _dump_mem,
    "randomize": _randomize,
    "random32": _random32,
    "randomrange": _random_range,
    "delay": _delay,
    "clrscr": _clrscr,
    "settextcolor": _ignore,
    "gotoxy": _ignore,
    "waitmsg": _wait_msg,
    "isdigit": _is_digit,
    "getmseconds": _get_mseconds,
    "readkey": _read_key,
    "parsedecimal32": _parse_decimal32,
    "parseinteger32": _parse_integer32,
}

# Routines that take dword arguments on the stack and remove them on return (stdcall).
STACK_ARGUMENTS = {
    "exitprocess": 1,
    "str_length": 1,
    "str_copy": 2,
    "str_compare": 2,
    "str_ucase": 1,
    "str_trim": 2,
}


# How the names are usually written, for display.
DISPLAY_NAMES = {
    "writestring": "WriteString", "writechar": "WriteChar", "writeint": "WriteInt",
    "writedec": "WriteDec", "writehex": "WriteHex", "crlf": "Crlf", "readint": "ReadInt",
    "readchar": "ReadChar", "readstring": "ReadString", "dumpregs": "DumpRegs",
    "exit": "exit", "exitprocess": "ExitProcess", "writebin": "WriteBin",
    "writebinb": "WriteBinB", "writehexb": "WriteHexB", "readdec": "ReadDec",
    "readhex": "ReadHex", "str_length": "Str_length", "str_copy": "Str_copy",
    "str_compare": "Str_compare", "str_ucase": "Str_ucase", "str_trim": "Str_trim",
    "dumpmem": "DumpMem", "randomize": "Randomize", "random32": "Random32",
    "randomrange": "RandomRange", "delay": "Delay", "clrscr": "Clrscr",
    "settextcolor": "SetTextColor", "gotoxy": "Gotoxy", "waitmsg": "WaitMsg",
    "isdigit": "IsDigit", "getmseconds": "GetMseconds", "readkey": "ReadKey",
    "parsedecimal32": "ParseDecimal32", "parseinteger32": "ParseInteger32",
}  # fmt: skip


def routine_addresses(mode: CpuMode) -> dict[str, int]:
    """Stub address of each routine, keyed by lowercase name, for the assembler."""
    base = mode.region("library_stubs").start
    return {name: base + index * STUB_SPACING for index, name in enumerate(ROUTINES)}


def install(emu: Emulator, console: Console) -> None:
    """Write the stubs and hook them. Runs after every load."""
    addresses = routine_addresses(emu.mode)
    handlers = {address: ROUTINES[name] for name, address in addresses.items()}
    for name, address in addresses.items():
        count = STACK_ARGUMENTS.get(name, 0)
        # `ret n` (C2 iw) removes stack arguments, as the callee does under stdcall.
        stub = b"\xc2" + (4 * count).to_bytes(2, "little") if count else RET
        emu.write_memory(address, stub)

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
