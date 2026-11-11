"""`int 21h` console services, selected by AH.

01h read a character into AL (echoed), 02h print DL, 09h print the '$'-terminated string at
EDX, 4Ch end the program, 40h print EDX as a signed decimal. 40h is an emu32 extension; in DOS
it means "write to file", which emu32 does not provide. It reads EDX, not EAX, because
setting AH would overwrite bits 8-15 of EAX (see docs/decisions.md D19).
"""

from __future__ import annotations

from emu32.emulator import Emulator, HookStop
from emu32.runtime.console import ENCODING, Console, InputCancelled
from emu32.runtime.memory_text import ServiceError, read_terminated

INT_INSTRUCTION_SIZE = 2  # CD ib


def handle_int21(emu: Emulator, console: Console) -> None:
    function = emu.register("AH")
    # EIP already points past `int 21h`; errors and retries refer to the int itself.
    here = emu.register("EIP") - INT_INSTRUCTION_SIZE
    try:
        if function == 0x01:
            char = console.read_char()
            console.write(char)
            emu.set_register("AL", 0x0D if char == "\n" else _byte(char))
        elif function == 0x02:
            console.write_bytes(bytes([emu.register("DL")]))
        elif function == 0x09:
            console.write_bytes(read_terminated(emu, emu.register("EDX"), ord("$"), "int 21h/09h"))
        elif function == 0x4C:
            emu.exit_program(emu.register("AL"))
        elif function == 0x40:
            console.write(str(_signed(emu.register("EDX"))))
        else:
            emu.fail(f"int 21h function {function:02X}h is not supported", here)
    except InputCancelled:
        raise HookStop(resume_at=here) from None
    except ServiceError as error:
        emu.fail(str(error), here)


def _byte(char: str) -> int:
    return char.encode(ENCODING, errors="replace")[0]


def _signed(value: int) -> int:
    return value - (1 << 32) if value & 0x8000_0000 else value
