# Differences and unsupported constructs

emu32 does not claim to behave exactly like any other assembler or emulator. This page lists
what it does differently and what it does not accept. When the assembler meets one of the
unsupported constructs below, it stops with a message that names the construct and, where
there is one, the supported form.

## Compared with 16-bit educational emulators

- **32-bit only.** Version 1 runs IA-32 code. 16-bit real-mode programs are not supported;
  a 16-bit mode is planned.
- **Flat memory, no segments.** Code, data and stack live in one 32-bit address space
  (code at `00400000`, data at `00500000`, stack below `00800000`). Segment registers are
  not used. `mov ax, @data` and `mov ds, ax` are not needed and are rejected with a hint.
- **Library routines for most I/O.** Console output and input use routines such as
  `WriteString` and `ReadInt`. A small set of `int 21h` services is provided for programs
  written in the DOS style.
- **`.model small` and `org`.** Accepted with a warning and treated as a flat program.
- **Memory protection.** Code is read-only and data cannot be executed. Writing into the code
  area or jumping into data stops the program with a message.

## Unsupported constructs

| Construct | Message points to |
|---|---|
| `@data`, segment register setup | remove the two lines |
| `lea dx, msg`, `mov dx, OFFSET msg` (an address in a 16-bit register) | use the 32-bit register: `lea edx, msg` |
| `SEGMENT`, `ENDS`, `ASSUME` | use `.data` and `.code` |
| `INVOKE` | push the arguments and use `CALL` |
| `.IF`, `.ELSE`, `.WHILE`, `.REPEAT` and the other high-level directives | use `CMP` and conditional jumps |
| `MACRO`, `ENDM` | not supported |
| `STRUCT`, `STRUC` | not supported |
| `LOCAL` | keep variables in `.data` or on the stack |
| `PROC` options such as `USES` or parameters | not supported; save registers with `PUSH` and `POP` |
| `DQ`, `QWORD`, `DT`, `TBYTE`, `REAL4`, `REAL8` | 64-bit, 80-bit and floating-point data are not supported |
| `EQU <text>` | text constants are not supported; use a number |
| `INCLUDE` of files other than `Irvine32.inc` | not supported |
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

- `int 21h` supports functions 01h, 02h, 09h and 4Ch as in DOS, plus 40h, which in emu32
  prints EDX as a signed decimal (in DOS, 40h writes to a file). Other functions stop the
  program with a message.
- The library routines are emu32's own implementations of the commonly used console
  routines. Details such as how `ReadInt` reports invalid input may differ from other
  libraries: emu32 sets OF=1 and returns 0.
- Carriage returns are not shown; a line feed starts a new line.
