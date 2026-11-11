# Changelog

Versions follow [semantic versioning](https://semver.org): within one major version,
programs that assemble and run keep working, so a course can use one version for a
whole semester.

## Unreleased

First release.

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
