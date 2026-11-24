"""`int 21h` console services, selected by AH (spec 8.2).

01h read a character with echo into AL; 02h print DL; 06h direct console I/O (DL = FFh
reads without waiting, ZF = 1 if nothing was typed); 07h and 08h read a character without
echo; 09h print the '$'-terminated string at DS:DX (COM, EXE) or EDX (flat); 0Ah buffered
input at DS:DX; 2Ah get date; 2Ch get time; 4Ch end the program. 40h prints EDX as a
signed decimal; it is an emu32 extension (in DOS it means "write to file", which emu32 does
not provide) and reads EDX, not EAX, because setting AH would overwrite bits 8-15 of EAX
(D19).
"""

from __future__ import annotations

import datetime

from emu32.emulator import Emulator, EmulatorError, HookStop
from emu32.runtime.console import ENCODING, Console, InputCancelled
from emu32.runtime.memory_text import ServiceError, read_terminated

INT_INSTRUCTION_SIZE = 2  # CD ib
ZERO_FLAG = 1 << 6
CR = 0x0D


def handle_int21(emu: Emulator, console: Console) -> None:
    function = emu.register("AH")
    # EIP already points past `int 21h`; errors and retries refer to the int itself.
    here = emu.register("EIP") - INT_INSTRUCTION_SIZE
    pointer = "DX" if emu.mode.is_16bit else "EDX"  # every segment is 0 in COM and EXE
    try:
        if function == 0x01:
            char = console.read_char()
            console.write(char)
            emu.set_register("AL", key_code(char))
        elif function == 0x02:
            console.write_bytes(bytes([emu.register("DL")]))
        elif function == 0x06:
            _direct_io(emu, console)
        elif function in (0x07, 0x08):
            emu.set_register("AL", key_code(console.read_char()))
        elif function == 0x09:
            console.write_bytes(
                read_terminated(emu, emu.register(pointer), ord("$"), "int 21h/09h")
            )
        elif function == 0x0A:
            _buffered_input(emu, console, emu.register(pointer))
        elif function == 0x2A:
            today = datetime.date.today()
            emu.set_register("CX", today.year)
            emu.set_register("DH", today.month)
            emu.set_register("DL", today.day)
            emu.set_register("AL", (today.weekday() + 1) % 7)  # DOS: 0 = Sunday
        elif function == 0x2C:
            now = datetime.datetime.now()
            emu.set_register("CH", now.hour)
            emu.set_register("CL", now.minute)
            emu.set_register("DH", now.second)
            emu.set_register("DL", now.microsecond // 10_000)
        elif function == 0x4C:
            emu.exit_program(emu.register("AL"))
        elif function == 0x40:
            console.write(str(_signed(emu.register("EDX"))))
        else:
            emu.fail(f"int 21h function {function:02X}h is not supported yet", here)
    except InputCancelled:
        raise HookStop(resume_at=here) from None
    except ServiceError as error:
        emu.fail(str(error), here)


def key_code(char: str) -> int:
    """The byte a program gets for a typed character; Enter is CR, as in DOS."""
    return CR if char == "\n" else char.encode(ENCODING, errors="replace")[0]


def set_zero_flag(emu: Emulator, on: bool) -> None:
    name = emu.mode.flags_register
    value = emu.register(name)
    emu.set_register(name, value | ZERO_FLAG if on else value & ~ZERO_FLAG)


def _direct_io(emu: Emulator, console: Console) -> None:
    dl = emu.register("DL")
    if dl != 0xFF:
        console.write_bytes(bytes([dl]))
        return
    char = console.try_read_char()
    set_zero_flag(emu, char is None)
    emu.set_register("AL", 0 if char is None else key_code(char))


def _buffered_input(emu: Emulator, console: Console, address: int) -> None:
    """DOS buffered input: byte 0 is the buffer size including the CR; DOS stores the
    count typed (without the CR) in byte 1, then the characters and a CR."""
    try:
        size = emu.read_memory(address, 1)[0]
    except EmulatorError:
        where = emu.mode.format_address(address)
        raise ServiceError(f"int 21h/0Ah: the buffer at {where} is outside memory") from None
    if size == 0:
        raise ServiceError("int 21h/0Ah: byte 0 of the buffer is 0; set it to the buffer size")
    line = console.read_line()
    data = line.encode(ENCODING, errors="replace")[: size - 1]
    console.write(data.decode(ENCODING))  # DOS echoes the characters; Enter gives only CR
    try:
        emu.write_memory(address + 1, bytes([len(data)]) + data + bytes([CR]))
    except EmulatorError:
        raise ServiceError("int 21h/0Ah: the buffer does not fit in memory") from None


def _signed(value: int) -> int:
    return value - (1 << 32) if value & 0x8000_0000 else value
