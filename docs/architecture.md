# Architecture

```
GUI (PySide6)            Session                 Emulator (Unicorn)
 editor window   --->     compile, load,  --->    registers, memory,
 emulator window          step, run, stop,        chunked run, hooks
 tool windows             breakpoints, history
                              |
                              v
                 Assembler (front-end -> Keystone, Capstone)
```

The GUI talks only to `Session`; it never imports Unicorn, Keystone or Capstone. Session,
emulator, assembler and runtime have no Qt imports, so they are tested without a window.

## Modules

| Path | Job |
|---|---|
| `cpu_mode.py` | Facts that differ between CPU modes: register names, memory map, engine modes. `MODE32` is the only mode so far. |
| `assembler/cleaner.py` | Strips comments, lowercases outside strings, converts numbers to hex. |
| `assembler/data_pass.py` | Packs `.data` into bytes and builds the symbol table. |
| `assembler/operands.py` | Expressions, `OFFSET`/`SIZEOF`/`LENGTHOF`/`TYPE`, and turning `mov eax, total` into `dword ptr [00500004]`. |
| `assembler/encode.py` | Sections and directives, one Keystone call for all code, the line map (Capstone), per-line error search, listing. |
| `emulator/core.py` | Unicorn wrapper: load, step, run in chunks, exact instruction count, breakpoints, memory access recording, run-time errors. |
| `emulator/history.py` | Step-back log: registers plus old bytes of every memory write. |
| `runtime/` | Console with blocking input, `int 21h` services, library routines on stub addresses. |
| `session.py` | Controller: load, reload, reset, step, step over, run, stop, step back, watches, trace records, a lock and live snapshots for the window. |
| `numbers.py` | Converter and calculator logic. |
| `gui/` | Editor and emulator windows, panels, table models, CPU view, tools, help, worker thread. |

## Running a program

1. `assemble()` returns a `Program`: code bytes, data bytes, entry address, symbols and the
   address-to-line map.
2. `Emulator.load()` maps the regions (exit stub, library stubs, code, data, stack), writes
   the program and pushes the exit stub address, so `ret` from `main` ends the program.
3. Run executes in chunks of 10,000 instructions with `emu_start(count=...)`. A basic-block
   hook counts instructions exactly; no Python runs per instruction. Breakpoints are code
   hooks limited to one address each.
4. Library calls land on a one-byte `ret` stub; a hook on the stub region runs the Python
   routine first. `int 21h` arrives through Unicorn's interrupt hook.
5. Single steps also record memory reads and writes, which feed step back and the trace
   record used by the Aux window and the CPU structure view.

## Threads

Commands run in a `QThread` (`gui/worker.py`). The session holds a lock while the engine
runs and publishes a register snapshot between chunks; the window shows that snapshot at
about 30 frames per second and reads the full state only when the engine is idle. Stop sets
a flag, calls `emu_stop` and wakes a blocked input read.

## Decisions

Every non-obvious choice, with measurements where they mattered, is in
[decisions.md](decisions.md).
