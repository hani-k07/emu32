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

## D29. Examples ship inside the package (2026-11-11)

Section 5.2 puts `examples/` at the repository root. Files outside the package do not reach
a `pip install`, so the examples live in `src/emu32/examples/` and are declared as package
data. The editor finds them with `importlib.resources`.

## D30. GUI module layout (2026-11-11)

Besides the modules in section 5.2, the GUI has `code_editor.py` (editor and gutter),
`highlighter.py`, `settings.py` (settings, recent files, app-data folder), `errors.py`
(error dialog and log), `theme.py`, `icons.py`, `templates.py` and `worker.py`.

## D31. Themes (2026-11-11)

Light and dark themes both set every palette color on the Fusion style, so the window looks
the same whatever the system's own light or dark setting is. Without a saved choice, the
theme follows the system setting. A render on a Windows machine in dark mode showed the
light theme mixing a dark editor with light syntax colors before this change.

## D32. App data, autosave and the log (2026-11-11)

Settings, the log (`emu32.log`) and autosave files live in the user's app-data folder
(`QStandardPaths.AppDataLocation`). The `EMU32_HOME` environment variable overrides it; tests
use it, and the portable build can use it to keep everything next to the program. Every
20 seconds each changed tab is written to `autosave/`; a clean exit deletes those files, so
their presence at start means emu32 did not close normally, and it offers to restore them.

## D33. Source file encoding (2026-11-11)

Files are written as UTF-8. Reading tries UTF-8 (with or without a byte order mark) first
and falls back to Windows-1252, which older course files often use; the status bar says so,
and the next save writes UTF-8.

## D34. Parts that come in later milestones (2026-11-11)

In M5, Emulate compiles and then says the emulator window comes in the next version (M6).
Calculator, Converter, ASCII table, the syntax reference and the tutorial are in the menus
but disabled or show a short note until M7. Toolbar icons are drawn at run time as colored
tiles with a symbol, so the project ships no image files.

## D35. Chunk size and a responsive window (2026-11-11)

A 1,000,000-step run with chunks of 100,000 instructions left the window thread with one
timer tick in one second: the block hook calls Python about 500,000 times a second, and
the window thread only got the GIL back when a chunk ended. Measured on Windows, Python 3.14:

| Chunk | Run time | Window ticks (10 ms timer) | Longest gap |
|---|---|---|---|
| 100,000 | 0.96 s | 1 | about 1 s |
| 10,000 | 0.99 s | 67 | 21 ms |
| 5,000 plus 1 ms pause | 1.29 s | 119 | 19 ms |

The default chunk is now 10,000 instructions: no measurable cost, and the window stays
responsive. A test runs 1,000,000 steps in the window and fails if the event loop is blocked
for more than 250 ms.

## D36. Reading state while the program runs (2026-11-11)

Unicorn must not be read from the window thread while the worker runs it. The session holds
a lock while the engine runs and publishes a register snapshot and the step count between
chunks. During a fast Run the window shows that snapshot at about 30 updates per second.
In step delay mode the lock is free between steps, so the window refreshes every panel then.
When a command ends, everything is refreshed.

## D37. Change markers (2026-11-11)

Changed registers, flags, variables and memory bytes get a `*` in their first column as well
as a background color, so a change is visible without color (section 8.8). Registers and
flags compare with their values before the last command. Memory marks bytes that differ from
what the panel showed before, which also covers bytes changed by a Run. The disassembly marks
the current instruction with `>` and breakpoints with `B`.

## D38. Emulator window layout (2026-11-11)

The tool windows of section 8.4 are dock panels: Screen at the bottom, Source on the right,
Aux, Vars, Debug, Stack and Flags tabbed with Source. The buttons in the bottom row show
them; each can float as its own window. The CPU structure view is a separate window. The
memory panel shows a 64 KB window of the address space at a time; the address box moves it.
The disassembly lists the whole program, decoded once per load, and shows library calls by
name (`call WriteString`). Step over (F10) is in the Debug menu, from M4.

## D39. Projector mode (2026-11-11)

View > Projector mode (Ctrl+Shift+P) switches to a high-contrast black and white theme and
scales the emulator window's fonts by 1.6. Ctrl+plus and Ctrl+minus scale further. The
editor keeps its own zoom.

## D40. CPU structure view details (2026-11-11)

Phases are shown in the order Fetch, Decode, Execute, Memory access; the last appears only
when the step touched data memory, and lists every access. Fetch: PC and AR hold the
instruction address and IR the instruction bytes. Decode: PC moves to the next sequential
instruction and IR adds the decoded text. Execute: PC is the real next EIP (after a jump),
AC is EAX, and the ALU shows the operation, its inputs and result in hex. Memory access: AR
is the data address and DR the data. Active parts get a thick outline and a `>` marker.

## D41. Help pages live in the package (2026-11-11)

Sections 8.6 and 13 put the tutorial and references in `docs/`. The app must show them after
a `pip install` or from the executable, and files outside the package are not installed, so
they live in `src/emu32/help/` (`quickstart.md`, `syntax.md`, `instructions.md`) as package
data. The README links to them. `docs/` keeps the project documents: decisions, differences,
architecture and classroom notes. A test assembles and runs the constructs the syntax page
shows; it caught one wrong example (a WORD array read into EAX) before release.

## D42. Examples (2026-11-11)

Eight original examples, each in the style it suits: sum of array, factorial (recursive,
reads input), bubble sort and find maximum (signed) use MASM style with library routines;
string reverse (with the stack) and simple loop use `int 21h` in MASM style; string print and
Fibonacci use Intel/NASM style. Golden tests check each one's full screen output and that
none produces an assembler warning.

## D43. Calculator and converter (2026-11-11)

The logic is in `emu32/numbers.py` (no Qt). The calculator accepts `0FFh`, `0xFF`, `1010b`,
`0b1010`, `377o`, `0o377` and decimals; operators `+ - * / mod and or xor not shl shr` and
their symbols, and parentheses. Results are shown at 8, 16 or 32 bits, signed and unsigned.
Division rounds toward minus infinity for negative operands; the help says so.

## D44. Saved window layout (2026-11-11)

Both windows save their size, position and panel layout on close and restore them at start
(P2 item "persisted window layout").

## D45. Control Flow Guard is off for emu32.exe (2026-11-12)

The first frozen build crashed with 0xC0000409 as soon as the program was loaded. With a
console build and faulthandler, the crash was inside `Uc.mem_map`, at the access violation
that Unicorn normally handles itself (D7). The PyInstaller launcher is built with Control
Flow Guard (DllCharacteristics bit 0x4000); `python.exe` is not. Unicorn recovers from that
fault with `longjmp`, and with CFG on, Windows ends the process at that jump. Clearing the
bit on a copy of the launcher made the self-test pass. `packaging/emu32.spec` clears it on
every build, so the launcher matches `python.exe`.

## D46. Installer (2026-11-12)

Inno Setup, as section 11 asks. Its license (read from `license.txt` in the upstream
repository) allows any use, including commercial, with the source public; conditions are
keeping its copyright notices. It is a zlib-style license, not on the OSI list. Inno Setup is
a build tool; only its installer runtime is inside `emu32-setup.exe`. The installer installs
per user (`{autopf}` resolves to `%LOCALAPPDATA%\Programs`) and offers all users when run as
administrator. It creates a Start Menu entry, an optional desktop shortcut and an optional
`.asm` association; the association is written to the user's registry (or the machine's for
an all-users install), which is the only place outside the install folder, app data and the
Start Menu.

## D47. Release pipeline and its checks (2026-11-12)

`.github/workflows/release.yml` runs on version tags, on pushes to `main` that change
packaging, and by hand. On a fresh Windows runner it runs the tests, builds the program
folder, runs `emu32.exe --self-test` (assemble and run an example, open both windows
offscreen), builds the installer, installs it silently for the current user, self-tests the
installed copy, checks the Start Menu entry, uninstalls, and checks nothing is left. It then
self-tests the portable folder from a fresh copy and checks it kept its data next to the
program. Only for a tag does it publish the zip with its SHA-256 in the release notes. The
runner is not a classroom PC; `docs/classroom.md` lists the manual check for one.

## D48. Version and pip install (2026-11-12)

The version is defined once, in `src/emu32/__init__.py`; `pyproject.toml` reads it, and the
release job fails if a tag does not match it. The package is not on PyPI yet, so the README
gives `pip install git+https://github.com/hani-k07/emu32.git`, which installs the same way;
`pip install emu32` needs the maintainer to publish to PyPI.

## D49. Portable mode and self-test (2026-11-12)

A `portable.txt` file next to `emu32.exe` keeps settings, the log and autosave in a `data`
folder there; if the folder cannot be written, the user's app-data folder is used. The
release zip's `portable/` folder includes the file. `emu32 --self-test` exits with 0 or 1 and
writes failures, including native crashes through faulthandler, to the log, since a
windowed program has no console.

## D50. Disassembly shows names (2026-11-12)

Jump and call targets inside the program show their label (`jbe base_case`,
`call factorial`), and library calls their routine name, instead of raw addresses.

## D51. Microsoft's C++ runtime in the Windows build (2026-11-12)

The Windows zip contains `vcruntime140*.dll` and `msvcp140*.dll`. Python and Qt for Windows
are built with Microsoft's compiler and need them; clean Windows installs do not reliably
have them, and installing Microsoft's redistributable would need administrator rights. They
are redistributable but not open source. Options considered: bundle them (chosen), require
them on the PC (breaks on clean lab PCs), rebuild everything with an open MinGW toolchain
(large and fragile), or ship no Windows binary (fails section 11). GPL-2.0's system-library
exception does not clearly cover a runtime that accompanies the executable; nearly every
GPL program shipping Python or Qt on Windows bundles it the same way. Decided with the
repository owner on 2026-11-12. The README and `THIRD_PARTY_NOTICES.md` state it. A fully
open toolchain build can follow later as a separate project.

## D52. Offline guarantee (2026-11-12)

A test fails if any emu32 module imports networking code (socket, ssl, urllib, http,
QtNetwork and similar); the only exception is the self-test's own guard. `--self-test`
replaces Python's socket functions with ones that refuse and record every attempt, and
fails if any was made, so each release build proves it ran without touching the network.
Links in the About and Welcome windows open the user's browser only when clicked.

## D53. 16-bit address registers (2026-11-12)

`lea dx, msg` and `mov dx, OFFSET msg` load only the low 16 bits of a 32-bit address, so a
following `int 21h` function 09h printed nothing and stopped with an error at address 0.
The assembler now rejects an address loaded into an 8- or 16-bit register and shows the
32-bit form (`lea edx, msg`). A run-time error for an address below 10000h adds the same
hint. Reading a WORD variable into DX (`mov dx, w`) is unaffected.

## D54. Screen window on output (2026-11-12)

When a program prints (an `int 21h` output function or a library routine), the Screen
window is shown and brought forward, also if it was closed or tabbed away. Input already
did this.

## D55. Release download test on several machines (2026-11-12)

After the build job, a second job runs on Windows Server 2022, Windows Server 2025 and
Windows 11 on ARM (x64 emulation). It takes the zip as a student would (for a tag, from the
public release link, checking the SHA-256 against the release notes), marks it as
downloaded from the internet, unpacks it into a folder with spaces and accented letters,
checks the contents, runs the portable copy, and installs into a folder with a non-ASCII
name, runs and uninstalls.

## D56. A reserve of references to None on Python 3.11 (2026-11-12)

CI on Ubuntu with Python 3.11 aborted after all tests passed: "none_dealloc: deallocating
None". Measured on 3.11, creating and freeing one `unicorn.Uc` loses about two references
to None (-406 over 200 instances, with no hooks and no memory mapped), so the cause is in
the unicorn 2.1.4 Python binding, not in emu32. Every program load creates a new `Uc`; a
few hundred loads in one process drained None to zero at interpreter exit. Python 3.12 and
newer make None immortal, so only 3.11 is affected. On 3.11, `emulator/core.py` holds
200,000 extra references to None (1.6 MB), enough for about 100,000 loads in one session.
The release builds use Python 3.13 and do not need it. The bug should be reported upstream.

## D57. Running again after a CPU fault (2026-11-12)

After a divide error, pressing Run or Step again hung the emulator. The interrupt hook
stops Unicorn in the middle of raising the exception, so the CPU still counted an exception
in progress; the next divide error became a double fault (interrupt 08h), and inside a
session the run never returned. After a CPU exception the emulator now restores a clean CPU
context and writes all registers back (since D62: a fresh Unicorn instance with the same
memory and registers). Running again reports the same error;
after the user fixes the cause (for example edits ECX), the program continues.

## D58. More library procedures (2026-11-12)

Testing programs for the course's labs 9 to 12 showed students need more of the console
library than section 7.4 lists. Added, written from their documented register use:
WriteBin, WriteBinB, WriteHexB, ReadDec, ReadHex, ReadKey, DumpMem, Clrscr, WaitMsg,
Delay, Randomize, Random32, RandomRange, IsDigit, GetMseconds, ParseDecimal32,
ParseInteger32, and the string procedures Str_length, Str_copy, Str_compare, Str_ucase and
Str_trim. The string procedures take stack arguments (called with INVOKE), so their stubs
are `ret n` instead of `ret`. SetTextColor and Gotoxy are accepted and ignored. Random
numbers start from a fixed seed, so a program prints the same numbers every run until it
calls Randomize. Not provided: WriteStackFrame, MsgBox, file procedures.

## D59. Advanced procedures (2026-11-12)

Lab 12 (advanced procedures) is built on MASM's procedure syntax, which emu32 rejected
before. Now supported, by expanding it into ordinary instructions in the assembler:

- `PROC USES regs, param:TYPE, ...`: entry code `push ebp`, `mov ebp, esp`, `sub esp, n`
  for LOCAL variables, then `push` for each USES register; at each `ret`, the reverse
  pops, `leave`, and `ret n` that removes the arguments (stdcall, MASM's default with
  `.model flat, stdcall` and the course library). Parameters live at `[ebp+8]` and up,
  LOCAL variables below EBP, each sized by its declared type.
- `INVOKE name, args`: pushes from last to first, then calls. `ADDR` gives `push OFFSET`
  for globals and `lea eax` plus `push eax` for LOCAL variables. 8- and 16-bit register
  arguments are zero-extended through EAX.
- `PROTO` is accepted and ignored; `PUBLIC` is ignored; `EXTERN` gets a clear message
  (one source file at a time).
- Labels inside a PROC are local to it, as in MASM, so procedures can reuse `next:` and
  `done:`; `name::` stays global. The disassembly shows them as `proc.label`.

One source line may now produce several instructions. They all map to that line, and the
line maps to the first of them, so breakpoints, stepping and the line map keep working; a
test steps through such code and back.

## D60. `rep movsd` (2026-11-12)

Keystone reads a bare `movsd` as the SSE2 instruction of the same name and rejects it. The
assembler adds the string form's operands (`dword ptr es:[edi], dword ptr [esi]`).

## D61. Course topic programs (2026-11-12)

`tests/course_topics/` holds four programs written for emu32 that cover the course's lab
topics 9 to 12: shifts, rotates, MUL and DIV; library procedures, extended addition and
decimal arithmetic; string instructions and two-dimensional arrays; advanced procedures.
Each runs in a test against its full expected output. The course's own lab programs, when
the instructor provides them, go to `tests/lab_programs/` (section 8.8).

## D62. Keystone keeps hex as its number base after NASM mode (2026-11-12)

The lab 12 test failed in about one full-suite run in four: `add eax, third` read past the
top of the stack. The assembled bytes differed between runs. Reproduced: after any program is
assembled in Intel/NASM mode, Keystone parses plain numbers as hex for the rest of the
process, even in new instances with Intel syntax set explicitly, so the generated
`[ebp+12]` became `[ebp+0x12]` and `ret 12` became `ret 18`. Numbers from source files were
never affected, because the cleaner already writes every number as `0x` hex (D12). All
generated text (parameter and LOCAL offsets, `ret n`, `sub esp, n`) now uses `0x` hex too.
A test assembles a NASM program first and checks that a MASM program's bytes do not change.

While searching for this, two other risks were removed, even though neither was the cause:
the clean CPU context of D57 is gone (after a CPU fault the emulator now rebuilds a fresh
Unicorn instance with the same memory and registers), and Python's cyclic garbage collector
is paused while Unicorn executes, so no finished instance is finalized inside a hook.
