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
