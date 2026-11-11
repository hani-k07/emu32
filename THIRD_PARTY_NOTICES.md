# Third-party notices

emu32 depends on the following packages. They are installed by pip and bundled in the
release executables. Their full license texts ship inside each package.

| Package | License | Project |
|---|---|---|
| Unicorn (CPU emulator engine) | GPL-2.0; Python binding BSD | https://www.unicorn-engine.org, https://github.com/unicorn-engine/unicorn |
| Keystone (assembler engine) | GPL-2.0-only; Python binding BSD-3-Clause | https://www.keystone-engine.org, https://github.com/keystone-engine/keystone |
| Capstone (disassembler engine) | BSD-3-Clause | https://www.capstone-engine.org, https://github.com/capstone-engine/capstone |
| PySide6-Essentials, shiboken6 (Qt for Python) | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only; used under GPL-2.0-only | https://pyside.org |
| Qt 6 (QtCore, QtGui, QtWidgets, bundled with PySide6) | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only; used under GPL-2.0-only | https://www.qt.io |

Development-only tools (not distributed): pytest (MIT), pytest-qt (MIT), ruff (MIT),
PyInstaller (GPL-2.0-or-later with bootloader exception).

See `docs/decisions.md` (D1) for how these licenses combine.

## Also inside the Windows release

The Windows zip is built with PyInstaller and Inno Setup. Besides the packages above it
contains:

| Component | License | Notes |
|---|---|---|
| Python runtime | Python Software Foundation License 2.0 | the interpreter and standard library |
| PyInstaller bootloader | GPL-2.0-or-later with the bootloader exception | `emu32.exe` itself |
| OpenSSL 3 | Apache-2.0 | part of Python's standard library; emu32 makes no network connections |
| libffi | MIT | used by Python's `ctypes` |
| Mesa llvmpipe (`opengl32sw.dll`) | MIT | Qt's software OpenGL fallback |
| Microsoft Visual C++ runtime (`vcruntime140*.dll`, `msvcp140*.dll`) | Microsoft Visual C++ Redistributable license | a Windows system library that Python and Qt need; redistributable, not open source |
| Inno Setup installer runtime | Inno Setup License (permissive, source at https://github.com/jrsoftware/issrc) | inside `emu32-setup.exe` only |
