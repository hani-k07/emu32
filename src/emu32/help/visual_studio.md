# Coming from Visual Studio

emu32 runs the 32-bit MASM programs written for Visual Studio and the Irvine32
library, without Visual Studio, without a project and without installing MASM.
Open the `.asm` file, press **F5** (Compile), then **Ctrl+F5** (Emulate).

## What carries over unchanged

- `INCLUDE Irvine32.inc` and `INCLUDE Macros.inc` (both built in), `.386`,
  `.model flat, stdcall`, `.stack 4096`, `.data`, `.data?`, `.const`, `.code`,
  `main PROC` ... `main ENDP`, `END main`.
- `ExitProcess PROTO, dwExitCode:DWORD` and `INVOKE ExitProcess, 0`, or `exit`.
- `BYTE`, `SBYTE`, `WORD`, `SWORD`, `DWORD`, `SDWORD`, `QWORD`, `DUP`, `?`,
  `LENGTHOF`, `SIZEOF`, `TYPE`, `OFFSET`, `PTR`, `LABEL`, `ALIGN`, `=`, `EQU`,
  `TEXTEQU`.
- Procedures: `USES`, stack parameters, `LOCAL`, `PROTO`, `INVOKE`, `ADDR`,
  `ENTER`/`LEAVE`, labels local to a procedure, `name::` global labels, `@@:`.
- `.IF`, `.ELSEIF`, `.ELSE`, `.ENDIF`, `.WHILE`, `.ENDW`, `.REPEAT`, `.UNTIL`,
  `.BREAK`, `.CONTINUE`.
- `MACRO`/`ENDM` with `LOCAL`, `:REQ` and default values; `mWrite`, `mWriteLn`,
  `mWriteString`, `mWriteSpace`, `mReadString`, `mGotoxy`, `mDumpMem`.
- `STRUCT`/`ENDS`, arrays of structures, `(Type PTR [esi]).Field`.
- `REAL4`, `REAL8`, `REAL10` and the x87 FPU instructions; WriteFloat, ReadFloat,
  ShowFPUStack. The FPU panel plays the part of Visual Studio's floating-point
  registers.
- Library procedures: WriteString, WriteChar, WriteDec, WriteInt, WriteHex,
  WriteBin, Crlf, ReadInt, ReadDec, ReadHex, ReadChar, ReadString, ReadKey,
  DumpRegs, DumpMem, Str_length, Str_copy, Str_compare, Str_ucase, Str_trim,
  Random32, RandomRange, Randomize, Delay, GetMseconds, Clrscr, WaitMsg, IsDigit,
  ParseDecimal32, ParseInteger32. SetTextColor and Gotoxy are accepted; the
  Screen window shows plain text.

## The debugger, side by side

| Visual Studio | emu32 |
|---|---|
| Registers window | Registers panel, with 16-bit and 8-bit parts and changed values marked |
| Memory window | Memory panel; type an address or a variable name |
| Watch window | Vars panel and watches |
| Disassembly | Disassembly panel, next to your own source |
| F10 / F11 | F8 single step, F10 step over |
| (no equivalent) | Shift+F8 step back, up to 10,000 steps |
| Breakpoints | click the line-number area in the editor, or double-click an instruction in Disassembly |
| Flags in the Registers window | Flags panel, one row per flag with its meaning |

## Differences to know

- Memory is flat and starts at fixed addresses: code at `00400000`, data at
  `00500000`, the stack ends at `00800000`. Addresses differ from a Windows
  process, values do not.
- One source file per program: `EXTERN` and several `.asm` files in one project
  are not supported.
- No Windows API beyond `ExitProcess`, no `MsgBox`, and no conditional assembly
  (`IF`, `REPT`, `FOR`).
- 16-bit DOS programs (`.model small`, `mov ax, @data`) are rejected with a hint:
  emu32 runs 32-bit code.

The assembler names any construct it does not support and says what to write
instead.
