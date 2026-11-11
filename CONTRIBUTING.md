# Contributing to emu32

Thank you for helping. Bug reports, examples, documentation fixes and code are all welcome.

## Setup

Python 3.11 or newer.

```
git clone https://github.com/hani-k07/emu32.git
cd emu32
python -m venv .venv
.venv\Scripts\activate          # Linux and macOS: source .venv/bin/activate
pip install -e ".[dev]"
git config core.hooksPath scripts/hooks
```

The last line turns on the commit message check (see below).

## Tests and checks

```
pytest -q
ruff check .
ruff format --check .
python scripts/check_repo_rules.py
```

CI runs the same on Windows and Ubuntu with Python 3.11 and 3.13. GUI tests run without a
screen (`QT_QPA_PLATFORM=offscreen`, set in `tests/conftest.py`). The whole suite takes
under a minute.

New behavior needs a test. CPU behavior is checked against the Intel manual, not against
another emulator.

## Git workflow

- Branch from `main`; one branch per feature or fix.
- Conventional Commit messages: `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `ci:`.
- Small commits, tests passing before each one.
- Merge into `main` with `--no-ff`. Never force-push and never rewrite pushed history.
- `scripts/check_repo_rules.py` rejects emojis, tool attribution lines and tracked
  local-only files; the commit message hook runs it on every message.

## Writing style

Plain, short sentences. Comments say why, not what. No emojis in code, comments, UI text,
docs or commits.

## Where things are

See [docs/architecture.md](docs/architecture.md). In short: `assembler/` turns source
into bytes, `emulator/` runs them with Unicorn, `runtime/` provides console services,
`session.py` ties it together, and `gui/` is the Qt interface, which talks only to the
session.

## Adding a library routine

1. Write the routine in `src/emu32/runtime/library_routines.py` as a function
   `(emu, console) -> None`. Read and set registers with `emu.register()` and
   `emu.set_register()`; print with `console.write()`; read input with
   `console.read_line()` or `console.read_char()`.
2. Add it to the end of `ROUTINES` (lowercase name) and to `DISPLAY_NAMES`. Adding at the
   end keeps every other routine's stub address the same.
3. Document it in the module docstring and in `src/emu32/help/syntax.md`.
4. Add a test in `tests/test_runtime.py`.

Write routines from their commonly documented behavior. Do not copy code from other
libraries.

## Clean-room rule

emu32 must stay free of other programs' internals. Do not use code, text, icons or
examples taken from EMU8086 or other emulators, and do not decompile or analyze them.
Behavior notes written by someone who used another program normally are fine; put them in
`docs/observations/` as text.

## Good first issues

- More example programs, with a golden test in `tests/test_examples.py`
- Virtual devices (the reserved menus in the emulator window)
- A 16-bit mode (`cpu_mode.py` is designed for a second mode)
- A strict mode that only accepts a chosen instruction set
- Release builds for Linux and macOS
- Translations of the help pages
