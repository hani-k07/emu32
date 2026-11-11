# emu32 in the classroom

## Putting emu32 on lab PCs

The [releases page](https://github.com/hani-k07/emu32/releases) has two downloads:

| Download | Contents and use |
|---|---|
| `emu32-<version>-windows.zip` | `emu32-setup.exe` and `README.txt`. The installer installs for the current user without administrator rights; run it as administrator to choose "all users" instead. `LICENSE` and `THIRD_PARTY_NOTICES.md` are installed with the program. |
| `emu32-<version>-portable.zip` | An `emu32` folder with the program, for use without installation. Copy the folder anywhere and run `emu32.exe`. |

Ways to deploy:

- **Installer per student account**: each student runs `emu32-setup.exe` once. It adds a
  Start Menu entry and an uninstall entry. Silent install for scripts:
  `emu32-setup.exe /VERYSILENT /CURRENTUSER`.
- **Installer for all users**: run as administrator, choose "Install for all users", or
  `emu32-setup.exe /VERYSILENT /ALLUSERS`.
- **USB stick or shared folder**: unzip the portable zip and copy its `emu32` folder. Its `portable.txt` file
  keeps settings, the log and autosaved work in a `data` folder next to `emu32.exe`. On a
  read-only share it falls back to each user's own profile automatically.

emu32 needs no internet connection. It makes no network calls, sends no usage data and does
not check for updates.

## Checking a release on a clean machine

Before a semester, check the version you plan to use on one lab PC (Windows 10 or 11)
without administrator rights and without network access:

1. Sign in as a normal student account. Disconnect the network.
2. Run `emu32-setup.exe`. Expect no administrator prompt. Finish with "Launch emu32".
3. In emu32: File > Examples > factorial, F5 (Compile), Ctrl+F5 (Emulate), F9 (Run). Type
   5 in the Screen window and press Enter. Expect `Factorial: 120`.
4. Close emu32. Open Settings > Apps, find emu32, and uninstall it. Expect the program
   folder (`%LOCALAPPDATA%\Programs\emu32`) and the Start Menu entry to be gone.
5. Copy the `emu32` folder from the portable zip to a USB stick, run `emu32.exe` from there, and repeat
   step 3.

The release build runs the same checks automatically (silent install for the current user,
a self-test of the installed and portable copies, and uninstall) on a fresh Windows virtual
machine.

## Pinning a version

Releases use semantic versioning. Pick one version for the semester and keep its zip; the
[changelog](../CHANGELOG.md) lists what changed between versions.

## What is supported

- 32-bit programs in MASM style (`.data`, `.code`, `PROC`, `INCLUDE Irvine32.inc`) and
  Intel/NASM style.
- The console routines and `int 21h` functions listed in Help > Syntax reference.
- Single step, step back, breakpoints, watches, and every panel described in the quick
  start.

What is not supported, and how emu32 differs from 16-bit educational emulators, is listed in
[differences.md](differences.md). Programs that use an unsupported construct stop at compile
time with a message that names it.

## Teaching in front of a class

- **Projector mode** (emulator window, View > Projector mode, Ctrl+Shift+P): large text
  and high contrast.
- Ctrl+plus and Ctrl+minus change the text size in both windows.
- Changed values are marked with `*` as well as a color, so they remain visible on
  projectors with poor color.
- The CPU structure window (CPU button) shows fetch, decode and execute for each step.

## Reporting a problem

Open an issue at https://github.com/hani-k07/emu32/issues with the emu32 version (Help >
About), the program that shows the problem, and what you expected. If emu32 showed an
error message, include the details from its "Copy details" button; the full log is in
`%APPDATA%\emu32\emu32.log` (or `data\emu32.log` in the portable `emu32` folder).
