"""The 16 colors of a PC text screen (attribute bits 0-3 foreground, 4-6 background).

These are the program's colors, not the window's, so they are the same in every theme.
Values are the usual VGA text-mode palette.
"""

TEXT_SCREEN_COLORS = (
    "#000000", "#0000AA", "#00AA00", "#00AAAA", "#AA0000", "#AA00AA", "#AA5500", "#AAAAAA",
    "#555555", "#5555FF", "#55FF55", "#55FFFF", "#FF5555", "#FF55FF", "#FFFF55", "#FFFFFF",
)  # fmt: skip
