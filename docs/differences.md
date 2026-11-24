# Differences and unsupported constructs

emu32 does not claim to behave exactly like any other assembler or emulator. This page lists
what it does differently and what it does not accept. When the assembler meets one of the
unsupported constructs below, it stops with a message that names the construct and, where
there is one, the supported form.

## Compared with 16-bit educational emulators

- **A 386 in real mode, not an 8086.** COM and EXE programs run on the CPU's 16-bit real
  mode (D81): 8086 instructions behave as on an 8086, and 386 instructions and 32-bit
  registers work as well. Instruction timing is not modelled.
- **One 64 KB area, segments 0.** COM and EXE programs get one 64 KB area at address 0
  with every segment register 0 and `@data` = 0. A program that loads another segment value
  (for example `0B800h` for video memory) stops with "reads memory outside the program's
  memory". An EXE program's `.data` starts at 100h, with the code after it.
- **32-bit flat programs** keep code at `00400000`, data at `00500000` and the stack below
  `00800000`; there, `mov ax, @data` is rejected with a hint.
- **Library routines for most I/O.** Console output and input use routines such as
  `WriteString` and `ReadInt`. A small set of `int 21h` services is provided for programs
  written in the DOS style.
- **No video memory or graphics modes.** `int 10h` covers teletype output and clearing
  the screen; `in` and `out` read 0 and do nothing.
- **Memory protection.** Code is read-only and data cannot be executed. Writing into the code
  area or jumping into data stops the program with a message.

## Unsupported constructs

| Construct | Message points to |
|---|---|
| `@data`, segment register setup | remove the two lines |
| `lea dx, msg`, `mov dx, OFFSET msg` (an address in a 16-bit register) | use the 32-bit register: `lea edx, msg` |
| `SEGMENT`, `ENDS`, `ASSUME` | use `.data` and `.code` |
| `.UNTILCXZ` with a condition | use `.UNTIL` |
| text in angle brackets (`FORC c, <ABC>`) | read without case, like names; use quotes to keep case |
| `IFDEF` of a variable or label | `IFDEF` knows constants, text macros, macros and structures |
| `EXITM <value>` (macro functions), the `%` expansion operator | not supported |
| nested `STRUCT` fields and `UNION` | use BYTE, WORD, DWORD or QWORD fields |
| `EXTERN`, `EXTERNDEF`: a program split over several source files | put every procedure in one file |
| `PROC C` and other calling conventions | procedures always use stdcall: they remove their own arguments |
| library procedures `WriteStackFrame`, `MsgBox`, `GetMaxXY` and file procedures | not provided |
| `WriteFloat` output | emu32's own format, `+1.2345000E+001` (eight significant digits) |
| `INCLUDE` of files other than `Irvine32.inc` and `Macros.inc` | not supported |
| jumps to `$+n` or `$-n` | put a label at the target (`jmp $` alone works) |
| non-ASCII characters in strings | not supported |
| doubled quotes inside a string (`'it''s'`) | use the other quote character: `"it's"` |

## Intel/NASM syntax mode

- A variable name stands for its address, as in NASM. Use `[name]` to read memory and give
  the size (`dword [name]`) when it cannot be inferred from a register.
- Supported: `section .data`, `section .bss`, `section .text`, `global`, `extern`, `bits`,
  labels with a colon, `db`, `dw`, `dd`, `times`, `resb`, `resw`, `resd`, `equ`.
- Not supported: NASM local labels starting with a dot, macros (`%macro`, `%define`).

## Console services

- `int 21h` supports functions 01h, 02h, 06h, 07h, 08h, 09h, 0Ah, 2Ah, 2Ch and 4Ch as in
  DOS, plus 40h, which in emu32 prints EDX as a signed decimal (in DOS, 40h writes to a
  file). `int 10h` supports 00h and 0Eh, `int 16h` 00h and 01h, and `int 20h` ends the
  program. Other functions stop the program with "int XXh function YYh is not supported
  yet".
- Text typed into the Screen window has no key positions; `int 16h` gives each character
  the US-keyboard scan code of the key that types it, or 0.
- The library routines are emu32's own implementations of the commonly used console
  routines. Details such as how `ReadInt` reports invalid input may differ from other
  libraries: emu32 sets OF=1 and returns 0.
- Carriage returns are not shown; a line feed starts a new line.
- `SetTextColor` and `Gotoxy` are accepted and do nothing: the Screen window is plain
  text without colors or cursor positions. `Clrscr` clears it.
- `INVOKE` passes every argument as a dword. `ADDR` of a LOCAL variable goes through EAX,
  as in MASM.
