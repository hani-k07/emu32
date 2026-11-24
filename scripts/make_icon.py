"""Write the emu32 logo to files.

    python scripts/make_icon.py build/emu32.ico              # the program's icon (packaging/)
    python scripts/make_icon.py build/wizard                 # installer images (packaging/)
    python scripts/make_icon.py docs/images/logo.png 256     # PNG at a given size
    python scripts/make_icon.py docs/images/logo.svg         # SVG
    python scripts/make_icon.py docs/images/banner-dark.svg  # README banner, dark or light

The drawing itself lives in src/emu32/gui/logo.py, so the files never differ from the app.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from emu32.gui.logo import (  # noqa: E402
    banner_svg,
    ico_bytes,
    logo_image,
    logo_svg,
    wizard_images,  # noqa: E402
)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    app = QGuiApplication([])  # QPainter needs it  # noqa: F841
    target = Path(sys.argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() == ".ico":
        target.write_bytes(ico_bytes())
    elif target.suffix == "":
        target.mkdir(parents=True, exist_ok=True)
        for name, image in wizard_images().items():
            image.save(str(target / name))
    elif target.suffix.lower() == ".svg":
        if target.stem.startswith("banner"):
            text = banner_svg("dark" if target.stem.endswith("dark") else "light")
        else:
            text = logo_svg()
        target.write_text(text, encoding="utf-8", newline="\n")
    else:
        logo_image(int(sys.argv[2]) if len(sys.argv) > 2 else 256).save(str(target))
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
