"""Write the emu32 logo to files: the .ico for the Windows build, a PNG for the README.

    python scripts/make_icon.py build/emu32.ico            # used by packaging/
    python scripts/make_icon.py docs/images/logo.png 256   # PNG at a given size

The drawing itself lives in src/emu32/gui/logo.py, so the files never differ from the app.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from emu32.gui.logo import ico_bytes, logo_image  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    app = QGuiApplication([])  # QPainter needs it  # noqa: F841
    target = Path(sys.argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() == ".ico":
        target.write_bytes(ico_bytes())
    else:
        logo_image(int(sys.argv[2]) if len(sys.argv) > 2 else 256).save(str(target))
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
