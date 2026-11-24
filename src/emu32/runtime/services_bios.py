"""BIOS services: `int 10h` video and `int 16h` keyboard (spec 8.2).

int 10h: 0Eh writes AL as on a teletype; 00h sets a video mode, which clears the screen;
02h and 03h set and read the cursor (DH = row, DL = column; page BH is ignored); 06h
scrolls a window up (AL lines, 0 = clear; BH = color for new lines; CH, CL to DH, DL);
09h writes AL with color BL, CX times, at the cursor without moving it; 13h writes CX
characters from ES:BP (COM, EXE: BP; flat: EBP) at row DH, column DL, in color BL, or
with a color byte after each character when bit 1 of AL is set; bit 0 moves the cursor.
int 16h: 00h (and 10h) waits for a key and returns its scan code in AH and its character
in AL; 01h (and 11h) reports a waiting key in AX with ZF = 0, or ZF = 1 when there is none,
and leaves the key for the next read.

Scan codes are those of a US keyboard (IBM PC set 1). Text typed into the Screen window has
no key positions, so each character gets the scan code of the key that types it; characters
without one get 0.
"""

from __future__ import annotations

from emu32.emulator import Emulator, EmulatorError, HookStop
from emu32.runtime.console import ENCODING, Console, InputCancelled
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
    screen = console.screen
    if function == 0x0E:
        char = emu.register("AL")
        if char != 0x07:  # BEL makes a sound on a PC; the Screen window has none
            console.write_bytes(bytes([char]))
    elif function == 0x00:
        console.clear_output()
    elif function == 0x02:
        screen.set_cursor(emu.register("DH"), emu.register("DL"))
    elif function == 0x03:
        row, column = screen.cursor()
        emu.set_register("DH", row)
        emu.set_register("DL", column)
        emu.set_register("CX", 0x0607)  # the usual text-mode cursor shape
    elif function == 0x06:
        screen.scroll_up(
            emu.register("AL"),
            emu.register("CH"),
            emu.register("CL"),
            emu.register("DH"),
            emu.register("DL"),
            emu.register("BH"),
        )
    elif function == 0x09:
        char = bytes([emu.register("AL")]).decode(ENCODING)
        count = emu.register("CX")
        screen.write_repeated(char, emu.register("BL"), count)
        console.log(char * min(count, 2000))
    elif function == 0x13:
        _write_string(emu, console, here)
    else:
        emu.fail(f"int 10h function {function:02X}h is not supported yet", here)


def _write_string(emu: Emulator, console: Console, here: int) -> None:
    mode, count = emu.register("AL"), emu.register("CX")
    address = emu.register("BP" if emu.mode.is_16bit else "EBP")
    with_colors = bool(mode & 2)
    try:
        data = emu.read_memory(address, count * (2 if with_colors else 1))
    except EmulatorError:
        where = emu.mode.format_address(address)
        emu.fail(f"int 10h/13h: the string at {where} is outside memory", here)
        return
    chars = data[::2] if with_colors else data
    colors = list(data[1::2]) if with_colors else [emu.register("BL")] * count
    text = bytes(chars).decode(ENCODING)
    screen = console.screen
    saved = screen.cursor()
    screen.write_at(emu.register("DH"), emu.register("DL"), text, colors)
    if not mode & 1:
        screen.set_cursor(*saved)
    console.log(text)


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
