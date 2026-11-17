# The emu32 logo

![emu32 logo](images/logo.png)

Square brackets, as around a memory operand (`mov eax, [esi]`), with a step triangle
between them, on a blue tile: what is in memory, one step at a time.

- The drawing is `src/emu32/gui/logo.py`. Change it there and nowhere else.
- `python scripts/make_icon.py build/emu32.ico` makes the Windows icon (the release
  workflow does this before the build); `python scripts/make_icon.py docs/images/logo.png 256`
  makes the PNG used in the README.
- Colors: the gradient runs from the dark theme's accent to the light theme's accent; the
  mark is white. Do not recolor it per theme.
- Keep clear space of a quarter of the tile's width around it. Do not stretch, rotate or
  outline it, and do not put the name inside the tile.
- Below 28 px the logo uses its own bolder proportions (see `draw_logo`); do not scale the
  large drawing down by hand.
- The logo is part of emu32 and under the same license (GPL-2.0-or-later).
