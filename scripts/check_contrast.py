"""Check the theme palettes against WCAG 2.1 contrast ratios.

Fails (exit 1) if, in any theme:
- normal text is below 4.5:1 on a background it is drawn on,
- a syntax color is below 4.5:1 on the editor background or the current-line highlight,
- a control outline, the focus ring or a marker is below 3:1 (WCAG 1.4.11).
Decorative dividers (`border`) are exempt, as WCAG allows. Standard library only.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

THEMES = Path(__file__).resolve().parent.parent / "src" / "emu32" / "gui" / "theme"

TEXT = 4.5
NON_TEXT = 3.0

# (foreground, background, minimum ratio, what it is)
PAIRS = [
    *[("text.primary", bg, TEXT, "main text") for bg in
      ("bg.base", "bg.panel", "bg.raised", "selection", "changed", "current-line")],
    *[("text.muted", bg, TEXT, "labels and hints") for bg in ("bg.base", "bg.panel", "bg.raised")],
    ("text.on-accent", "accent", TEXT, "text on primary buttons"),
    *[("accent", bg, TEXT, "links") for bg in ("bg.base", "bg.panel")],
    *[(state, bg, TEXT, "status text") for state in ("ok", "warn", "error")
      for bg in ("bg.base", "bg.raised")],
    *[(f"syn.{kind}", bg, TEXT, "syntax color") for kind in
      ("instruction", "register", "number", "string", "comment", "directive", "label")
      for bg in ("bg.base", "current-line")],
    *[("border.control", bg, NON_TEXT, "control outline") for bg in
      ("bg.base", "bg.panel", "bg.raised")],
    *[("accent", bg, NON_TEXT, "focus ring") for bg in ("bg.raised",)],
    ("error", "bg.panel", NON_TEXT, "breakpoint marker"),
    ("accent", "bg.panel", NON_TEXT, "bookmark marker"),
]  # fmt: skip


def luminance(hex_color: str) -> float:
    channels = [int(hex_color.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def ratio(first: str, second: str) -> float:
    light, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def palettes() -> dict[str, dict[str, str]]:
    found = {}
    for name in ("dark", "light", "contrast"):
        spec = importlib.util.spec_from_file_location(name, THEMES / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        found[name] = module.PALETTE
    return found


def check(verbose: bool = False) -> list[str]:
    failures = []
    for theme, palette in palettes().items():
        for fg, bg, minimum, what in PAIRS:
            value = ratio(palette[fg], palette[bg])
            line = f"{theme:8} {fg:16} on {bg:13} {value:5.2f} (needs {minimum}) {what}"
            if value < minimum:
                failures.append(line)
            elif verbose:
                print("ok  " + line)
    return failures


def main() -> int:
    failures = check(verbose="-v" in sys.argv)
    for line in failures:
        print("LOW " + line)
    print(f"{len(failures)} contrast failures" if failures else "all contrast checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
