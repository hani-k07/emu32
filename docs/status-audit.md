# Status audit

A0 audit: 2026-11-24, `main` at `6d42b1d`, version 0.11.0, against the master
specification. Updated after each milestone; the latest update is at the end.

## Update after A1 and B1 (version 0.12.0)

- A1: `*PROMPT*.md` is ignored and blocked by the rules script; decision D80 records the
  owner's choice of COM as the default model.
- B1 (program models): **Done.** `ProgramModel` with `COM_MODEL`, `EXE_MODEL`,
  `FLAT_MODEL` in `cpu_mode.py`; COM and EXE run in 16-bit real mode (D81); 64 KB region,
  `int 20h` at offset 0, 2-byte return address `0000` at FFFEh; hello world runs in all
  three models (`tests/test_program_models.py`).
- B2 (assembler): **Partial.** Done: model detection, COM image layout with data in
  place, EXE layout, `@data` = 0, `#make_com#`/`#make_exe#`/`name "..."`, 8086 behavior
  (2-byte `call`/`ret`, `loop` on CX, string instructions on SI/DI/CX, `pusha` 16 bytes,
  `jcxz`), `xlat`/`retn`, `in`/`out` warning, the `[bp+4]` parameter test, 16-bit flag
  tests. Open: `seg`, `include 'emu8086.inc'` (needs the owner), BCD and every jump
  mnemonic tested in the COM model, `org` other than at the start.
- B3: `int 20h` done; `int 21h/09h` reads DS:DX. `0Ah`, `int 10h`, `int 16h`, the 80 x 25
  screen: still missing.
- B5/B6: New File dialog offers COM (default), EXE, flat, flat with library, empty; the
  Registers and Stack panels follow the model. Model selector, status-bar model, run-state
  pill: still missing.
- Tests: 460 passed.

## A0 findings

Status words: **Done**, **Partial**, **Missing**, **Broken**. "Evidence" names a test, a file,
or what was run.

## What was run

| Check | Result |
|---|---|
| `pytest -q` | 419 passed in 33 s |
| `ruff check .`, `ruff format --check .` | clean |
| `scripts/check_repo_rules.py` | passes |
| `scripts/check_contrast.py` | passes |
| CI on `main` and the v0.11.0 release run | green, including install tests on Windows 2022, 2025 and 11-ARM |
| Probe programs through `Session` (COM, EXE, `in`/`out`, `int 10h`, `int 21h/0Ah`, `daa`, `xlat`) | results below |

Probe results:

| Program | Result |
|---|---|
| COM: `org 100h`, `mov dx, offset msg`, `int 21h/09h`, `ret`, data after `ret` | does not assemble: "unknown name 'msg'", "data definitions belong in the .data section" |
| EXE: `.model small`, `mov ax, @data`, `mov ds, ax`, `mov dx, offset m` | does not assemble: "@data is a 16-bit segment value ... Remove 'mov ax, @data'", "dx is a 16-bit register and cannot hold the 32-bit address" |
| `in al, 60h` / `out 61h, al` | runs; reads 0, no notice shown |
| `int 10h/0Eh` | stops: "interrupt 10h is not supported" |
| `int 21h/0Ah` | stops: "int 21h function 0Ah is not supported" |
| `daa` | runs |
| `xlat` | does not assemble: "unknown instruction 'xlat'" |

## The main finding

emu32 today is a **32-bit flat-model tool aimed at Visual Studio / Irvine32 MASM courses**.
The specification's first requirement, COAL-lab programs in the **COM and EXE models**
(`org 100h` ... `ret`, `@data`, 16-bit pointers, 8086 behavior of `loop`, `call`, string
instructions), is **not implemented**. `cpu_mode.py` has one mode (`MODE32`) with the flat
memory map; there is no `ProgramModel` interface, no COM or EXE model, no 64 KB low region,
no PSP `int 20h`, no 2-byte return address and no `0x67`/`0x66` compatibility pass. Most of
the flat-model work, the debugger, the GUI and the release pipeline are done and tested.

## Milestones

| ID | Status | Evidence and notes |
|---|---|---|
| A0 | Done | this file |
| A1 | Partial | hooks, `check_repo_rules.py`, license check done; `.gitignore` gaps (see hard rules); the local session-notes file exists but points to the old spec |
| B1 Core and program models | Partial | flat model, step, chunked run, `max_steps`, run-time errors: done (`test_emulator_core.py`, `test_session.py`, `test_worker.py`). `ProgramModel` with COM and EXE: **Missing** |
| B2 Assembler | Partial | flat MASM is extensive (`test_assembler.py`, `test_masm_features.py`, `tests/vs_programs`). Model detection, 8086 behavior (section 7.4), `xlat`/`retn` spelling maps, `#make_com#`, `org` placement: **Missing** |
| B3 Runtime | Partial | `int 21h` 01h, 02h, 09h, 4Ch, 40h done (`test_runtime.py`). `int 20h`, `int 21h/0Ah`, `int 10h`, `int 16h`, P1 `int 21h` functions, 80 x 25 screen with attributes: **Missing** |
| B4 Session and debugger | Done (P2 open) | breakpoints, step over, step back (10,000), reset, Stop, watches, worker thread, trace records (`test_session.py`, `test_worker.py`). Run to cursor (P2): Missing |
| B5 Editor window | Partial | editor, error list, gutter, autosave and restore, recent files, examples, find and replace, tabs, welcome dialog: done (`test_editor_window.py`). New-file dialog offers flat templates only (no COM, no EXE); no program-model selector or model in the status bar |
| B6 Emulator window | Partial | registers, memory, disassembly, source, screen, stack, flags, vars, Aux, Debug, FPU, CPU buttons; 1,000,000-step run stays responsive (test in `test_emulator_window.py`). Missing: 16-bit register panel and "Show 32-bit" toggle, run-state pill, "planned" tooltip on disabled menus, change-highlight fade with Reduce motion |
| B7 P1 features | Partial | CPU structure window (`cpu_view.py`, phase stepping), macros, flat library routines, converter, ASCII, calculator, help: done. BCD runs (`tests/course_topics/lab10_library_extended_bcd.asm`). P1 interrupts: Missing |
| B8 Design system | Partial | tokens, dark and light, contrast check, no color literals (rules script), original logo with `.ico` (D79). Missing: bundled monospace font (uses the system fixed font), SVG logo and banner, installer wizard images, change fade, recorded HiDPI check at 125/150 percent and 1366 x 768. Icons are original QPainter drawings, not a third-party set (see decisions to confirm) |
| B9 Compatibility and docs | Partial | README, `classroom.md`, `differences.md`, `architecture.md`, `design.md`, `brand.md`, CONTRIBUTING, SECURITY. Missing: `tests/lab_programs/`, `docs/coal-compat.md`, `index.md`, `ui-checklist.md`, `github-setup.md`, `ideas.md`, `docs/observations/`, `scripts/make_screenshots.py`, `scripts/make_demo_gif.py`, social preview. Syntax and instruction references live in `src/emu32/help/` (shown in the app), not `docs/` |
| B10 Release | Partial | onedir build, per-user installer, offline, install and uninstall tested on three Windows images (`release.yml`). Release layout differs from 15.1: two zips (main zip = setup + README; separate portable zip) per D67 |
| B11 Final verification | Missing | not started |

## P0 / P1 / P2 items

| Item | Priority | Status | Evidence |
|---|---|---|---|
| COM model (section 6.1) | P0 | Missing | probe above; `cpu_mode.py` |
| EXE model (6.2) | P0 | Missing | probe above |
| Flat model (6.3) | P0 | Done | `cpu_mode.py` regions match the table; `test_emulator_core.py` |
| Flat segments (6.4) | P0 | Partial | flat: `mov ds, ax` runs and addresses stay flat; COM and EXE: missing with their models |
| Directives and syntax (7.2), flat | P0 | Done | `test_assembler.py`, `test_masm_features.py` |
| `org`, `#make_com#`, `name "..."`, `include 'emu8086.inc'` | P0 | Missing | `org` is ignored with a warning (`encode.py:242`) |
| Instruction dictionary (7.3) | P0 | Partial | families tested in `test_instructions.py`, `test_flags.py`; `xlat`, `retn` spellings missing; `in`/`out` run without the one-time notice |
| 8086 behavior (7.4) | P0 | Missing | no compatibility pass |
| Line map with prefixes, errors with lines | P0 | Done | `test_assembler.py` |
| Listing (7.5 step 10) | P2 | Done | `Session.listing`, Save listing in the editor |
| Registers and flags (8.1), flat | P0 | Done | `RegistersPanel`, `FlagsPanel` |
| 16-bit register view and "Show 32-bit" toggle | P0 | Missing | |
| `int 20h`, `int 21h/0Ah`, `int 10h/0Eh` | P0 | Missing | probe above |
| `int 21h` 01h, 02h, 09h, 4Ch | P0 | Done | `test_runtime.py` |
| `int 21h` 06h-08h, 2Ah, 2Ch; `int 10h` 00h-13h; `int 16h` | P1 | Missing | |
| `int 21h/40h` (print EBX) | P1 | Done | `services_int21.py` |
| 80 x 25 screen with cursor and colors (8.3) | P0 | Partial | screen is a text log with input line; no grid, cursor addressing or attributes |
| Library routines (8.4) | P1 | Done | `library_routines.py`, `tests/vs_programs` |
| Run-time errors (8.5) | P0 | Done | `test_session.py`, `test_user_programs.py` |
| Debugger (8.6) incl. step back, trace | P0/P1 | Done | `test_session.py` |
| Welcome dialog (9.1) | P1 | Done | `WelcomeDialog` |
| New-file dialog with COM/EXE/flat (9.2) | P0 | Partial | flat templates and Intel checkbox only |
| Editor window (9.3) | P0 | Partial | all but model selector and model in status bar |
| Emulator window (9.4) | P0 | Partial | see B6 |
| CPU structure window (9.5) | P1 | Done | `cpu_view.py`, `test_tools_and_help.py` |
| Tools (9.6), Help (9.7), About (9.8) | P1 | Done | `tools.py`, `help_window.py`, `AboutDialog` |
| Design tokens, themes, contrast (10.1-10.5) | P1 | Done | `gui/theme/`, `check_contrast.py` in CI |
| Default theme dark (10.1) | P1 | Differs | light is the default since D77, at the owner's request |
| Bundled monospace font (10.3) | P1 | Missing | `fixed_font()` uses the system font |
| Change fade and Reduce motion (10.6) | P1 | Partial | marker and highlight present, no fade |
| Icon set (10.7) | P1 | Differs | original drawn icons (`icons.py`), no third-party set |
| Logo SVG, `.ico`, PNG (10.7) | P1 | Partial | `.ico` and PNG from `gui/logo.py`; no SVG, banner or social preview |
| HiDPI and 1366 x 768 (10.8) | P1 | Not recorded | |
| Lab readiness (11): offline, autosave, no tracebacks, UTF-8, portable | P0 | Done | `test_offline.py`, autosave tests, `gui/errors.py`, portable self-test in `release.yml` |
| Flag edge cases (11) | P0 | Done | `test_flags.py` |
| Projector mode, zoom (11) | P1 | Done | `test_emulator_window.py` projector test |
| COM templates and examples (12) | P0 | Missing | 11 flat examples exist |
| Lab programs (13.2) | P0 | Missing | `tests/lab_programs/` does not exist; flat course programs in `tests/vs_programs`, `tests/course_topics` |
| GUI smoke tests (13.1) | P0 | Partial | `test_gui_smoke.py` runs one theme; theme switching is tested in `test_editor_window.py`, but the smoke run is not repeated in both |
| Manual checklist (13.3) | P1 | Missing | no `docs/ui-checklist.md` |
| Release zip (15.1) | P0 | Differs | two zips (D67) |
| Installer (15.2) | P0 | Done, wizard images missing | `emu32.iss` |
| pip install (15.3) | P1 | Done | README; `pyproject.toml` entry point |
| CI (15.4) | P0 | Done | `ci.yml` runs rules, contrast, ruff, pytest on Windows and Ubuntu |
| Performance (4.2) | P0 | Partial | 1,000,000-step run measured (`decisions.md` lines 63, 277, 553); cold start, 200-line compile, single-step latency and idle memory not recorded as a set |

## Hard rules

| Rule | Finding |
|---|---|
| 2.1 open source, public repo | repository is public; GPL-2.0-or-later; `THIRD_PARTY_NOTICES.md` present. Repository description has a double space ("for  32-bit") |
| 2.2 clean-room | no material from other emulators found; README states independence; `docs/reference/` ignored |
| 2.3 attribution | `git log --all` has no co-author trailers, tool-generated footers or assistant names; 129 commits, all hani-k07. `commit-msg` hook active (`core.hooksPath scripts/hooks`) |
| 2.4 emojis, style | `check_repo_rules.py` passes |
| 2.6 `.gitignore` | **Gap:** `git check-ignore` does not match `EMU32-MASTER-PROMPT.md`; the pattern is `PROMPT*.md`, the spec asks for `*PROMPT*.md`. Same gap in `BLOCKED_PATHS` of `check_repo_rules.py`. Nothing is tracked by mistake today |
| 2.6 local session-notes file | exists, untracked and ignored; points to `EMU32-PROMPT.md`, needs the new spec name and milestone |
| Tracked local-only files | none (`git ls-files` checked) |
| Secrets | none found by the rules script |

## Decisions that conflict with the specification

These were made earlier at the owner's request or from measurements. The specification
says it wins; each needs a yes or no before it is changed.

1. **Default program model.** Spec: COM. Current: flat with Irvine32 (the Visual Studio goal).
2. **Default theme.** Spec: dark. Current: light (D77, owner's request).
3. **Release layout.** Spec: one zip with `emu32-setup.exe`, `portable/`, README, licenses.
   Current: two zips (D67, owner's request).
4. **`max_steps` default.** Spec: 1,000,000. Current: 100,000,000, because an ordinary
   student program hit the 1,000,000 limit (D65). Proposal: keep it.
5. **Icon set.** Spec: a third-party set such as Lucide or Tabler. Current: original drawn
   icons, which need no license. Proposal: keep them.

## Proposed finishing order

| Order | Work | Effort |
|---|---|---|
| 1 | A1: `.gitignore` and rules-script pattern, local session notes, repository description | small |
| 2 | B1: `ProgramModel` interface; COM and EXE models (64 KB region, PSP `int 20h`, 2-byte return) | large |
| 3 | B2: model detection, `org` placement, `@data`, 16-bit pointers, section 7.4 prefixes, `xlat`/`retn`, `#make_com#` | large |
| 4 | B3: `int 20h`, `int 21h/0Ah`, `int 10h/0Eh`, then the 80 x 25 screen and P1 interrupts | medium to large |
| 5 | B5/B6: COM and EXE templates and examples, model selector, 16-bit register panel, 32-bit toggle, run-state pill | medium |
| 6 | B9: `tests/lab_programs/` (needs the owner's programs), `coal-compat.md`, missing docs, screenshot and GIF scripts | medium |
| 7 | B8: bundled font, SVG logo and banner, wizard images, fade, HiDPI pass | medium |
| 8 | B10/B11: release layout as decided, performance set, final verification | small to medium |

## Needs the owner

- Answers to the five conflicts above.
- COAL lab programs with expected output for `tests/lab_programs/`, and observation notes
  in `docs/observations/` (text only).
- Whether the lab uses `include 'emu8086.inc'` macros (section 2.2 requires confirmation).
