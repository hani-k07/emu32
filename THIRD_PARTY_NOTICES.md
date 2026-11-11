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
