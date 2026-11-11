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
Consequence for M8: the macOS build is made on an Intel runner and runs on Apple Silicon
under Rosetta; `pip install emu32` on a native arm64 Python builds keystone from source
(needs CMake). Revisit if upstream publishes an arm64 wheel.

## D5. Repository rule checks (2026-11-11)

`scripts/check_repo_rules.py` scans tracked files and every commit message for attribution
strings, emojis and obvious secrets, and fails if an assistant or local-only path is tracked.
`.gitignore`, the script itself and its test are exempt from the text scan because they must
name the blocked strings. The `commit-msg` hook lives in `scripts/hooks/`; enable it per clone
with `git config core.hooksPath scripts/hooks`.
