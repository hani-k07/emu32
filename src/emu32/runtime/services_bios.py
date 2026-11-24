"""BIOS services: `int 10h` video and `int 16h` keyboard (spec 8.2).

int 10h: 0Eh writes AL as on a teletype; 00h sets a video mode, which clears the screen.
int 16h: 00h (and 10h) waits for a key and returns its scan code in AH and its character
in AL; 01h (and 11h) reports a waiting key in AX with ZF = 0, or ZF = 1 when there is none,
and leaves the key for the next read.

Scan codes are those of a US keyboard (IBM PC set 1). Text typed into the Screen window has
no key positions, so each character gets the scan code of the key that types it; characters
without one get 0.
"""

from __future__ import annotations

from emu32.emulator import Emulator, HookStop
from emu32.runtime.console import Console, InputCancelled
from emu32.runtime.services_int21 import INT_INSTRUCTION_SIZE, key_code, set_zero_flag


def _scan_codes() -> dict[str, int]:
    table: dict[str, int] = {}
    rows = (
        (0x02, "1234567890-=", "!@#$%^&*()_+"),
        (0x10, "qwertyuiop[]", "QWERTYUIOP{}"),
        (0x1E, "asdfghjkl;'`", 'ASDFGHJKL:"~'),
        (0x2B, "\\zxcvbnm,./", "|ZXCVBNM<>?"),
    )
    for first, plain, shifted in rows:
        for offset, (a, b) in enumerate(zip(plain, shifted, strict=True)):
            table[a] = table[b] = first + offset
    table.update({"\n": 0x1C, " ": 0x39, "\b": 0x0E, "\t": 0x0F, "\x1b": 0x01})
    return table


SCAN_CODES = _scan_codes()


def key_word(char: str) -> int:
    """AX for a key: scan code in AH, character in AL."""
    return SCAN_CODES.get(char, 0) << 8 | key_code(char)


def handle_int10(emu: Emulator, console: Console) -> None:
    function = emu.register("AH")
    here = emu.register("EIP") - INT_INSTRUCTION_SIZE
    if function == 0x0E:
        char = emu.register("AL")
        if char != 0x07:  # BEL makes a sound on a PC; the Screen window has none
            console.write_bytes(bytes([char]))
    elif function == 0x00:
        console.clear_output()
    else:
        emu.fail(f"int 10h function {function:02X}h is not supported yet", here)


def handle_int16(emu: Emulator, console: Console) -> None:
    function = emu.register("AH")
    here = emu.register("EIP") - INT_INSTRUCTION_SIZE
    try:
        if function in (0x00, 0x10):
            emu.set_register("AX", key_word(console.read_char()))
        elif function in (0x01, 0x11):
            char = console.peek_char()
            set_zero_flag(emu, char is None)
            if char is not None:
                emu.set_register("AX", key_word(char))
        else:
            emu.fail(f"int 16h function {function:02X}h is not supported yet", here)
    except InputCancelled:
        raise HookStop(resume_at=here) from None
