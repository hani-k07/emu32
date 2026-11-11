# Changelog

Versions follow [semantic versioning](https://semver.org): within one major version,
programs that assemble and run keep working, so a course can use one version for a
whole semester.

## Unreleased

- New toolbar icons: original line drawings, larger, in theme colors.
- The editor opens with a blank document ready for typing.
- Emulator window: icon controls and matching panel headings.

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
