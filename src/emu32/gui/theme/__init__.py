"""Design system: tokens, palettes, the stylesheet and the theme manager (docs/design.md)."""

from emu32.gui.theme.theme_manager import (
    CHOICES,
    DEFAULT_THEME,
    PALETTES,
    apply,
    color,
    current_name,
    token,
)

__all__ = ["CHOICES", "PALETTES", "apply", "color", "current_name", "DEFAULT_THEME", "token"]
