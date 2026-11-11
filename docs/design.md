# Design system

Every color, size and font setting in the interface comes from the tokens in
`src/emu32/gui/theme/`. Widgets name a token (`theme.color("accent")`); they never write a
color. `scripts/check_repo_rules.py` fails if GUI code outside the theme folder contains a
color literal, and `scripts/check_contrast.py` fails if a palette breaks the contrast rules.
Both run in CI.

## Files

| File | Holds |
|---|---|
| `tokens.py` | token names, spacing, radius, type scale |
| `dark.py`, `light.py` | the two themes a user can choose; dark is the default |
| `contrast.py` | the high-contrast palette used by projector mode |
| `stylesheet.py` | one Qt stylesheet template, filled from a palette |
| `theme_manager.py` | applies a theme (palette, stylesheet, UI font) and hands out colors |

## Color tokens

| Token | Dark | Light | Use |
|---|---|---|---|
| `bg.base` | `#111318` | `#FFFFFF` | window and editor background |
| `bg.panel` | `#171A21` | `#F4F5F7` | panels, tool windows, gutter |
| `bg.raised` | `#1E222B` | `#ECEEF2` | toolbar, menus, headers |
| `border` | `#2A2F3A` | `#D5D9E0` | dividers (decorative) |
| `border.control` | `#6B7486` | `#7C8494` | outlines of inputs and buttons |
| `text.primary` | `#E6E9EF` | `#1B1F27` | main text |
| `text.muted` | `#9AA3B2` | `#555E6D` | labels, hints, line numbers |
| `text.on-accent` | `#0B1220` | `#FFFFFF` | text on accent buttons and icons |
| `accent` | `#4F9CFF` | `#1F5FBF` | focus ring, primary button, links, active parts |
| `selection` | `#2D4F7C` | `#C8DBF7` | selected text and rows |
| `ok` | `#4CC38A` | `#1D7A4B` | finished, success |
| `warn` | `#E5B454` | `#8A5A00` | paused, warnings, error lines in the gutter |
| `error` | `#F0646E` | `#C2313B` | errors, breakpoints |
| `changed` | `#2B3A55` | `#FFF0B3` | a value changed by the last step |
| `current-line` | `#1C2432` | `#EEF3FB` | current execution or cursor line |
| `syn.instruction` | `#7AB4FF` | `#1F4FB3` | instructions |
| `syn.register` | `#D3A6F7` | `#7A2E8E` | registers |
| `syn.number` | `#F0B072` | `#9A4400` | numbers |
| `syn.string` | `#8FD9A6` | `#23702A` | strings |
| `syn.comment` | `#8E98AA` | `#5F6775` | comments |
| `syn.directive` | `#FF8F88` | `#B3261E` | directives |
| `syn.label` | `#F2D479` | `#755600` | library routine names |

The dark values start from the polish brief; `border.control` was raised from `#5C6575` to
`#6B7486` because the brief's value gave 2.7:1 on `bg.raised`, below 3:1. `border.control`
and `text.on-accent` are added tokens: controls need a visible outline even though dividers
are decorative, and text on the accent color needs its own color to stay readable.

## Contrast rules

Checked by `scripts/check_contrast.py` (WCAG 2.1 formula), for dark, light and contrast:

- 4.5:1 for normal text: `text.primary` on every background it is drawn on (including
  selection, changed and current line), `text.muted` on the three backgrounds,
  `text.on-accent` on `accent`, `accent` as link text, and `ok`, `warn`, `error` as status
  text.
- 4.5:1 for every syntax color on `bg.base` and on `current-line`.
- 3:1 for non-text parts that identify a control or state (WCAG 1.4.11): control
  outlines, the focus ring, breakpoint and bookmark markers.
- `border` is decorative (it separates areas that also differ in background), so it is
  exempt, as WCAG allows.

Color is never the only signal: changed values also get a `*` marker, the current
instruction a `>`, breakpoints a `B` or a dot in the gutter.

## Spacing, shape, type

- Spacing: 4, 8, 12, 16, 24 px and nothing else.
- Corner radius 6 px for buttons, inputs, menu items and cards; 0 for editors and tables.
- One thin border (1 px); focus is a 2 px `accent` outline.
- Type scale 11, 12, 13, 15, 18 pt. Interface text 11 pt in the system font. Editor and
  monospace panels 12 pt (the bundled monospace font arrives in polish milestone P2).
- The stylesheet sets no font sizes, so font zoom and projector mode keep working.

## Themes

- Dark is the default. On the first start emu32 follows the system setting when it can read
  it (light stays light) and uses dark when it cannot. After that the choice in Options is
  remembered.
- Light uses the same token names. Projector mode switches to the high-contrast palette and
  larger fonts, and back again.
- Switching theme takes effect at once, also for colors drawn in code (gutter, syntax,
  tables, toolbar icons).
