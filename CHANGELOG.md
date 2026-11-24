# Changelog

Versions follow [semantic versioning](https://semver.org): within one major version,
programs that assemble and run keep working, so a course can use one version for a
whole semester.

## 0.16.1 (2026-11-24)

- Fixed: the build's self-test still looked for the examples in their old folder, so the
  0.16.0 build stopped before publishing. 0.16.0 was never released; 0.16.1 has its
  changes. A test now runs the self-test on every commit.

## 0.16.0 (2026-11-24, not released)

- New: 14 COM examples (hello world, read a key, sum of an array, compare and branch,
  LOOP, string reverse, stack parameters with BP, a macro, buffered input, factorial,
  bubble sort, find maximum, Fibonacci, 32-bit multiply in a 16-bit program) and 2 EXE
  examples. The Examples menu groups them by model, COM first, with a level and a
  description.
- New: a Model box in the editor toolbar (Auto, COM, EXE, 32-bit flat). The status bar
  shows the model, Ready/Edited/Compiled/Errors, the line and column, and the file name.
- New: the emulator shows the run state (Ready, Running, Paused, Finished, Error, Waiting
  for input), and COM/EXE programs have a "Show 32-bit registers" box.

## 0.15.0 (2026-11-24)

- New: the Screen window is an 80 x 25 text screen with a cursor and 16 colors. The plain
  text of everything printed is in the Output tab next to it. Click the screen and type
  to send keys to the program.
- New `int 10h` services: 02h and 03h (set and read the cursor), 06h (scroll or clear a
  window), 09h (character with color), 13h (string with colors).
- New: the library routines Gotoxy and SetTextColor move the cursor and set the color.
- Step back restores the screen.

## 0.14.0 (2026-11-24)

- New DOS services: `int 21h` 0Ah (read a line into a buffer), 06h (direct console I/O),
  07h and 08h (read without echo), 2Ah (date), 2Ch (time).
- New BIOS services: `int 10h` 0Eh (print AL) and 00h (set mode, clears the screen);
  `int 16h` 00h (wait for a key, with scan code) and 01h (check for a key).
- Changed: an unsupported interrupt or function stops with "int XXh function YYh is not
  supported yet" and the line.
- Docs: the Syntax reference explains the COM, EXE and flat program models.

## 0.13.0 (2026-11-24)

- Changed: each release is one download, `emu32-<version>-windows.zip`, with the
  installer, a `portable` folder for use without installing, `README.txt` and the
  licenses. The separate portable zip is gone.

## 0.12.1 (2026-11-24)

- Changed: the default theme is dark again. Light is a choice in Options and is remembered.
- Changed: the compile message names the program model and counts a COM program's data
  separately ("COM: 8 bytes of code, 3 bytes of data"); "1 byte" instead of "1 bytes".

## 0.12.0 (2026-11-24)

COAL-lab programs: COM and EXE programs run as written, and COM is the default.

- New: COM programs (`org 100h` ... `ret`) and EXE programs (`.model small`, `mov ax,
  @data`, `int 21h/4Ch`). They run as on an 8086 (a 386 in real mode): `call` and `ret`
  use 2-byte return addresses, so `[bp+4]` is the first parameter; `loop` counts CX
  (CX = 0 means 65,536 times); string instructions use SI, DI and CX. 32-bit registers
  still work in the same program.
- New: the program model is detected from the source (`org`, `.model`, `#make_com#`,
  `#make_exe#`). The New File dialog offers COM (default), EXE, 32-bit flat and flat with
  library routines.
- New: `int 20h` ends a program; `int 21h/09h` reads DS:DX in COM and EXE programs.
- New: the Registers panel shows AX ... SS, IP and FLAGS with their bytes and their
  32-bit registers for COM and EXE programs; the Stack panel shows words.
- New: `xlat` and `retn`; `in` and `out` read 0 with one warning.

## 0.11.0 (2026-11-17)

- emu32 has a logo: square brackets around a step triangle on a blue tile. It is the icon
  of the program, its windows, the taskbar, the installer and the desktop shortcut, and it
  is shown in the About window.

## 0.10.3 (2026-11-12)

- Changed: the default theme is now light (brighter panels and highlights). Dark is still
  available in Options and is remembered.
- Changed: the Registers panel columns are now labeled "32-bit", "Low 16", "Bits 15-8" and
  "Bits 7-0", with a tooltip on each, so it is clear that AX, AH and AL are parts of the
  32-bit register and not a 16-bit mode. The program was always 32-bit.
- Fixed: in projector mode and when zooming, the Registers, Memory and Disassembly column
  titles and values were cut off ("egiste", "00400..."). The columns now follow the font.
- Fixed: the About window cut off text ("Capstone (disassembler)", the independence
  notice) and squeezed the "Built with" list when the system font was wide.
- New high-resolution README screenshots (including projector mode, help and tools), a
  security policy and ten heavier regression programs. No other change to the program.

## 0.10.2 (2026-11-12)

- Fixed: after Emulate, the emulator window's Run, Single step, Step back, Reload and
  Reset stayed greyed out until a program had run once, so a newly loaded program could
  not be started.

## 0.10.1 (2026-11-12)

- Release checks download the published zips through the GitHub API, so they pass while
  the repository is private. No change to the program.

## 0.10.0 (2026-11-12)

Runs the MASM programs written for Visual Studio courses with the Irvine32 library.

- MASM course features: macros (with mWrite and the other course macros built in),
  `.IF`/`.ELSEIF`/`.ELSE`, `.WHILE`, `.REPEAT`/`.UNTIL`, `.BREAK`/`.CONTINUE`, `STRUCT`,
  `QWORD`, `LABEL`, `ALIGN`, `TEXTEQU` and `@@` labels.
- `AND`, `OR`, `XOR`, `NOT`, `SHL`, `SHR` in constant expressions.
- Help > Coming from Visual Studio; three new examples; the Memory address box takes a
  variable name.
- Floating point: REAL4/REAL8/REAL10 data, the x87 FPU, WriteFloat, ReadFloat,
  ShowFPUStack, an FPU panel, and step back over FPU instructions.
- Conditional assembly and repeat blocks: IF/IFB/IFIDN/IFDEF/ELSEIF/ELSE, REPT, FOR,
  FORC, WHILE, EXITM; EQ/NE/LT/LE/GT/GE in constant expressions.
- New toolbar icons: original line drawings, larger, in theme colors.
- The editor opens with a blank document ready for typing.
- Emulator window: icon controls and matching panel headings.
- About window: license, the engines with their versions and licenses, and the link.

## 0.9.1 (2026-11-12)

- Long programs run much faster: after the first 200,000 instructions a run no longer
  counts each instruction, so a 50-million-instruction program finishes in about 2 seconds.
  The status bar then shows "at least N instructions".
- The default run limit is now 100,000,000 instructions (was 1,000,000).
- The emulator window refreshes about four times faster; table headers are no longer cut off.
- The ASCII codes window shows all 256 codes on one screen.
- The release has two downloads: `emu32-<version>-windows.zip` with only the installer and
  README.txt, and `emu32-<version>-portable.zip` for running without installing.

## 0.9.0 (2026-11-12)

First public release, for testing with course material before 1.0.

- Assembler for MASM style and Intel/NASM style 32-bit programs, with every error listed
  by line number and plain messages for unsupported constructs.
- Emulator based on Unicorn: single step, step over, step back (10,000 steps), run with a
  step delay, breakpoints, watches, a one-million-step limit and Stop.
- Console library routines (`WriteString`, `WriteInt`, `ReadInt`, ...) and `int 21h`
  functions 01h, 02h, 09h, 4Ch and 40h.
- Editor: tabs, syntax coloring, breakpoints, bookmarks, find and replace, autosave and
  restore after a crash, recent files, templates.
- Emulator window: registers, memory, disassembly, screen, source, stack, variables, flags,
  trace and a CPU structure teaching view; projector mode.
- Converter, calculator, ASCII table, quick start tutorial, syntax and instruction
  references, and eight example programs.
- Windows installer (per user, no administrator rights) and a portable folder.
- Works fully offline; the release build checks that no network connection is attempted.
- The Screen window comes forward when a program prints.
- Advanced procedures: `PROC USES`, stack parameters, `LOCAL`, `INVOKE`, `ADDR` and
  `PROTO`; labels inside a procedure are local to it.
- More library procedures: WriteBin, WriteBinB, WriteHexB, ReadDec, ReadHex, ReadKey,
  DumpMem, Clrscr, WaitMsg, Delay, Randomize, Random32, RandomRange, IsDigit,
  GetMseconds, ParseDecimal32, ParseInteger32 and the Str_ procedures.
- Fixed: running again after a divide error no longer hangs; `rep movsd` assembles.
- `lea dx, msg` and `mov dx, OFFSET msg` (16-bit habits) are reported at compile time with
  the 32-bit form to use instead.
