"""Design tokens: every color name, size and font setting the interface uses.

Widgets read colors only through these names (`theme.color("accent")`), never as literals;
`scripts/check_repo_rules.py` enforces that outside this folder. See docs/design.md.
"""

from __future__ import annotations

# Color token names. Every palette (dark.py, light.py, contrast.py) defines all of them.
COLOR_TOKENS = (
    "bg.base",  # window and editor background
    "bg.panel",  # side panels, tool windows, gutter
    "bg.raised",  # toolbar, menus, headers, cards
    "border",  # dividers (decorative)
    "border.control",  # outline of inputs and buttons (must be visible: 3:1)
    "text.primary",
    "text.muted",  # labels, hints, line numbers
    "text.on-accent",  # text on accent-colored buttons
    "accent",  # focus ring, primary button, links, active parts
    "selection",  # text and row selection
    "ok",  # finished, success
    "warn",  # paused, warnings
    "error",  # errors, breakpoints
    "changed",  # background of a value changed by the last step
    "current-line",  # current execution or cursor line
    "syn.instruction",
    "syn.register",
    "syn.number",
    "syn.string",
    "syn.comment",
    "syn.directive",
    "syn.label",
)

SPACING = (4, 8, 12, 16, 24)  # px; no other values
RADIUS = 6  # px for buttons, inputs and cards; 0 for editors and tables
TYPE_SCALE = (11, 12, 13, 15, 18)  # pt
UI_POINT_SIZE = 11  # buttons, menus, labels
EDITOR_POINT_SIZE = 12  # editor and monospace panels
EDITOR_LINE_HEIGHT = 1.4
