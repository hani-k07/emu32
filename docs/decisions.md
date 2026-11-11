# Decisions

Each entry records a choice, the facts behind it, and the date.

## D1. Dependency licenses and project license (2026-11-11)

Checked from the installed packages and the upstream repositories.

| Dependency | Version checked | License of what ships in the wheel | Source |
|---|---|---|---|
| unicorn | 2.1.4 | Native engine (`unicorn.dll` / `.so`): GPL-2.0. Python binding metadata says BSD. | [COPYING](https://github.com/unicorn-engine/unicorn/blob/master/COPYING) |
| keystone-engine | 0.9.2 | Native engine: GPL-2.0 only (README: "without the 'any later version' clause"), commercial license also offered. Python binding: BSD-3-Clause. | [COPYING](https://github.com/keystone-engine/keystone/blob/master/COPYING), [README](https://github.com/keystone-engine/keystone/blob/master/README.md) |
| capstone | 5.0.9 | BSD-3-Clause | [LICENSE.TXT](https://github.com/capstone-engine/capstone/blob/next/LICENSE.TXT) |
| PySide6-Essentials, shiboken6 | 6.12.0 | `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` (PyPI metadata) | [pyside.org](https://pyside.org), [PyPI](https://pypi.org/project/PySide6-Essentials/) |

The two engines are GPL-2.0 (keystone explicitly GPL-2.0 only). PySide6 is offered under
GPL-2.0-only as one of its three options, so there is no LGPL-3.0 versus GPL-2.0 conflict:
the distributed program uses PySide6 under GPL-2.0-only. Capstone (BSD-3-Clause) is compatible
with GPL-2.0.

Decision: emu32's own code is licensed **GPL-2.0-or-later**. Distributed builds, which bundle
the GPL-2.0-only engines, are therefore covered by GPL-2.0 as a whole. `THIRD_PARTY_NOTICES.md`
lists each dependency.

## D2. PySide6-Essentials instead of PySide6 (2026-11-11)

Only QtCore, QtGui and QtWidgets are needed. The `PySide6` meta package also pulls in Addons,
WebEngine and Pdf (several hundred MB). Depending on `PySide6-Essentials` keeps installs and
PyInstaller builds small. All Qt modules used must come from the Essentials set, which Qt
offers under GPL-2.0.

## D3. Python versions (2026-11-11)

`requires-python >= 3.11`. All four dependencies install from wheels on Python 3.14 on Windows
(checked locally). Keystone 0.9.2 and unicorn 2.1.4 ship `py3-none` / `abi3` wheels, so they
do not depend on the Python minor version. CI tests 3.11 and 3.13 on Ubuntu and Windows.

## D4. Keystone wheels by platform (2026-11-11)

`pip download --only-binary=:all:` for keystone-engine 0.9.2 found wheels for Windows x64,
Linux x86_64 (manylinux1) and macOS x86_64 (10.14+). There is **no macOS arm64 wheel**.
Version 1 releases target Windows only, so this does not block a release. It matters when
macOS builds are added (P2): build on an Intel runner and run under Rosetta, or build
keystone from source (needs CMake). `pip install emu32` on a native arm64 Python also builds
keystone from source.

## D5. Repository rule checks (2026-11-11)

`scripts/check_repo_rules.py` scans tracked files and every commit message for attribution
strings, emojis and obvious secrets, and fails if an assistant or local-only path is tracked.
`.gitignore`, the script itself and its test are exempt from the text scan because they must
name the blocked strings. The `commit-msg` hook lives in `scripts/hooks/`; enable it per clone
with `git config core.hooksPath scripts/hooks`.

## D6. Counting instructions during Run (2026-11-11)

Run executes in chunks with `emu_start(..., count=N)`. Unicorn does not report how many
instructions ran when it stops early (program end, fault, Stop). To keep the instruction
counter exact, the emulator attaches a basic-block hook and counts the instructions in each
block (decoded once with Capstone and cached). After an early stop, the instructions of the
last block that did not run are subtracted.

Measured on Windows, one million instructions: no hook 0.03 s, block hook 0.4 to 1 s
(depends on block length), per-instruction hook 1.4 s. The block hook is a middle ground: it
is not per instruction (section 4, rule 1) and a full 1,000,000-step run stays near one
second in the worker thread. Tests check the count is exact for chunk sizes 1 to 25.

## D7. pytest faulthandler disabled (2026-11-11)

On Windows, `Uc.mem_map` raises an access violation that Unicorn handles itself; the program
continues normally (checked with a plain script). Python's faulthandler still prints a
"Windows fatal exception" dump for it, which buries real test output. `addopts` in
`pyproject.toml` turns the plugin off.

## D8. Emulator module layout (2026-11-11)

Section 5.2 lists `memory_map`, `registers`, `flags`, `hooks` and `history` under
`emulator/`. The memory map and the partial-register table are facts of the CPU mode, so
they live in `cpu_mode.py` (section 5.3). Hooks live in `core.py` next to the state they
update. `flags.py` holds the flag bit table. `history.py` comes with step back in M4.

## D9. Memory permissions (2026-11-11)

Code and stub regions are read and execute only. Data and stack are read and write only.
A write into code or a jump into data stops the program with a message that names the area,
which is easier for a student to understand than silent self-modifying code.

## D10. CpuMode as a frozen dataclass (2026-11-11)

`CpuMode` holds the mode facts as fields; `MODE32` is the one instance. A 16-bit mode is a
second instance. The service set (section 5.3) is added in M3 together with the services.

## D11. Assembler module layout (2026-11-11)

Section 5.2 lists `cleaner`, `directives`, `data_pass`, `operands`, `encode`, `linemap` and
`errors`. Directive handling, the code pass and the line map share one small state object, so
they live together in `encode.py`. The other modules match the list.

## D12. Number conversion (2026-11-11)

The cleaner rewrites every number outside strings to `0x` hex: `0Ah`, `1010b`, `10d` and
plain decimals. Keystone does not accept the `b` suffix, and converting plain decimals means
a leading zero (`010`) is always decimal, as in MASM. Digits right after a dot are left alone
so `.386` stays a directive. Character constants (`'A'`) are converted in operands and
expressions; in `db` they are strings.

## D13. `$` and label arithmetic (2026-11-11)

Keystone does not accept `$`. In code, the assembler puts a hidden label before the
instruction and uses it in place of `$`, so `jmp $` works. Keystone also rejects a jump to
`label+n`, so `jmp $+2` is reported as unsupported with a hint. In data and constants `$` is
the current data address, so `len = $ - msg` works.

## D14. Finding every assembly error (2026-11-11)

Keystone stops at the first error and does not say which line it was on. When the whole
program fails, each instruction is assembled again on its own, followed by definitions of
every code label, so references still resolve. Every failing line is reported. Keystone
error codes become plain messages: unknown instruction, unknown name, operand sizes that do
not match, invalid operand.

## D15. Telling instructions from data and names (2026-11-11)

The list of x86 mnemonics comes from Capstone (`insn_name` for every instruction id). It
separates `push dword [x]` from a variable named `push`, and rejects variable and label
names that are instruction names, such as `str` or `test`.

## D16. Entry point (2026-11-11)

Order: the label named by `END name`, then `main`, then `_start` (Intel/NASM style), then the
first code label, then the start of the code section. Section 6.1 names `main` first; `END`
is checked before it because it is the explicit choice when both exist.

## D17. Intel/NASM syntax mode (2026-11-11)

Keystone runs with its NASM syntax option. The front-end still splits sections and packs
data, because data must go to the data region, which is writable, and code to the read-only
code region. A variable name stands for its address, with no size inference. See
`docs/differences.md` for the supported directives.

## D18. Library routine stubs (2026-11-11)

Each routine's stub is one `ret` byte in the library-stub region. A code hook limited to that
region runs the Python routine, then the real `ret` returns to the caller. Section 7.4
describes popping the return address and setting EIP from the hook; Unicorn 2.1.4 does not
handle an EIP write inside a code hook reliably (a test run crashed with an invalid read), and
letting the CPU execute `ret` has the same effect. When a routine ends the program, fails or
is waiting for input that gets cancelled, the `ret` does not run, so a later Run calls the
routine again. The stub `ret` counts as one executed instruction.

A routine name written alone as a statement (`exit`) is assembled as a call to it, so the
common `exit` line works.

## D19. `int 21h` function 40h prints EDX, not EAX (2026-11-11)

Section 7.3 says 40h prints EAX. AH selects the function, and AH is bits 8 to 15 of EAX, so
`mov ah, 40h` always overwrites part of the number: -15 printed as -48911. The service reads
EDX instead, which matches 02h (DL) and 09h (EDX). This changes the spec; revert if EAX is
required for compatibility with course material.

## D20. Console behavior (2026-11-11)

- Bytes are shown with code page 437, so box-drawing characters from DOS-style programs
  display as expected.
- Carriage returns are dropped; a line feed starts a new line. `13, 10` prints one line break.
- Line input (`ReadInt`, `ReadString`) echoes the typed line followed by a line break, so the
  screen reads like a terminal session. `ReadChar` does not echo; `int 21h` 01h does.
- Input blocks the emulator thread. Cancelling a read (Stop) ends the run as a normal Stop
  and the read happens again on the next Run.

## D21. Library routine behavior (2026-11-11)

Written from the commonly documented behavior, not from any library source:
`WriteInt` prints a leading sign (`+5`, `-5`); `WriteHex` prints eight digits; `ReadInt` sets
OF=1 and EAX=0 when the line is not a 32-bit integer; `ReadString` takes the buffer size in
ECX, stores at most ECX-1 characters and a 0, and returns the count in EAX; `ReadChar`
returns 0Dh for Enter; `ExitProcess` takes its exit code from the stack argument.

## D22. Service set and the CPU mode (2026-11-11)

Section 5.3 lists the service set in the `CpuMode` interface. The runtime reads 32-bit
registers by name (EDX, EAX), which a 16-bit mode would replace with segment:offset
addressing, so it would need its own runtime module anyway. The stub addresses come from the
mode's memory map. The service set is not modelled in `CpuMode` until a second mode exists.

## D23. Breakpoints (2026-11-11)

Each breakpoint is a Unicorn code hook limited to its one address, so Run keeps its speed:
the check happens in C and no Python runs at other addresses. A run or step that starts on
a breakpoint executes that instruction. Breakpoints are kept by source line; on load and
reload they are mapped to addresses again, and a line without an instruction moves to the
next line that has one.

## D24. Single steps and library routines (2026-11-11)

A single step on `call WriteString` also runs the routine, so a step never stops inside a
library stub, which has no source line. Step over on a call into the program's own code
runs until the call returns to the same stack frame (the stack pointer is compared, so a
recursive call returning to the same address from a deeper frame does not stop it).
Breakpoints inside the called procedure still stop.

## D25. Step back (2026-11-11)

History entries hold the main registers, the old bytes of every memory write in the step
(captured by a memory-write hook attached only during single steps, plus writes made by
services such as `ReadString`), the step counter, the ended flag and the console length.
Step back restores all of these, so printed output disappears again. Input that a step
consumed is not given back. Limit 10,000 entries; Run and step over clear the history.
Step delay mode keeps it, because it is made of single steps.

## D26. Trace records (2026-11-11)

Each single step produces a record: address, bytes, text, source line, registers before and
after, memory accesses (address, read or write, bytes, old bytes) and the ALU operation for
arithmetic, logic, shift and compare instructions. ALU inputs come from Capstone's decoded
operands and the registers before the step; MUL, IMUL, DIV and IDIV with one operand also
show EAX. The last 100 records are kept for the Aux window. Run does not produce records,
because that would need a per-instruction hook.

## D27. Worker thread and step delay (2026-11-11)

`gui/worker.py` holds the only Qt code for running: a `QThread` worker that calls Session
methods and reports results as signals. The step delay loop itself lives in
`Session.run_with_delay`, which waits on a threading event, so Stop also cuts a long pause
short and the loop is testable without Qt. `Console.cancel` only acts while a read is
waiting, so a Stop pressed during computation cannot cancel a later read.

## D28. Watch expressions (2026-11-11)

A watch may use registers (including AX, AL and the other parts), variables (the value of
the first element, signed for SBYTE, SWORD and SDWORD), constants, numbers in any accepted
format, `+ - * / mod`, `OFFSET`, `SIZEOF`, `LENGTHOF`, `TYPE`, and `[expression]`, which
reads a dword from memory. Errors come back as short messages.
