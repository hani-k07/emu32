import struct

from PySide6.QtGui import QImage

from emu32.gui.logo import SIZES, app_icon, ico_bytes, logo_image


def test_the_logo_is_drawn_at_every_size(qtbot):
    icon = app_icon()
    assert {s.width() for s in icon.availableSizes()} == set(SIZES)
    for size in SIZES:
        image = logo_image(size)
        center, corner = image.pixelColor(size // 2, size // 2), image.pixelColor(0, 0)
        assert center.alpha() == 255, size  # the tile covers the middle
        assert corner.alpha() == 0, size  # rounded corners stay transparent


def test_small_sizes_keep_the_brackets_and_triangle_apart(qtbot):
    # On the middle row of the 16 px icon: bracket, gap, triangle, gap, bracket.
    image, row = logo_image(16), 8
    light = [image.pixelColor(x, row).lightness() > 200 for x in range(16)]
    runs = sum(1 for x in range(16) if light[x] and (x == 0 or not light[x - 1]))
    assert runs == 3, light


def test_the_ico_file_holds_every_size(qtbot):
    data = ico_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    assert (reserved, kind, count) == (0, 1, len(SIZES))
    for index, size in enumerate(SIZES):
        side, _, _, _, _, bits, length, offset = struct.unpack_from(
            "<BBBBHHII", data, 6 + 16 * index
        )
        assert (side or 256) == size and bits == 32
        image = QImage.fromData(data[offset : offset + length], "PNG")
        assert image.width() == size == image.height()
    assert offset + length == len(data)


def test_the_about_window_shows_the_logo(qtbot):
    from PySide6.QtWidgets import QLabel

    from emu32.gui.dialogs import AboutDialog

    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    assert not dialog.findChild(QLabel, "logo").pixmap().isNull()


def test_svg_logo_and_banners_are_valid_and_match_the_drawing(qtbot):
    import xml.etree.ElementTree as ET

    from emu32.gui.logo import _shapes, banner_svg, logo_svg

    root = ET.fromstring(logo_svg())
    ns = "{http://www.w3.org/2000/svg}"
    polylines = root.findall(f".//{ns}polyline")
    assert len(polylines) == 2 and root.find(f".//{ns}polygon") is not None
    first = [tuple(float(v) for v in p.split(",")) for p in polylines[0].get("points").split()]
    assert first == [tuple(map(float, point)) for point in _shapes(False)["brackets"][0]]
    for name in ("light", "dark"):
        banner = ET.fromstring(banner_svg(name))
        assert banner.find(f".//{ns}text").text == "emu32"


def test_wizard_images_have_inno_setup_sizes(qtbot):
    from emu32.gui.logo import wizard_images

    images = wizard_images()
    assert (images["side100.bmp"].width(), images["side100.bmp"].height()) == (164, 314)
    assert (images["small100.bmp"].width(), images["small100.bmp"].height()) == (55, 55)
    assert images["side200.bmp"].width() == 328 and images["small200.bmp"].width() == 110


def test_committed_svgs_are_up_to_date():
    """docs/images/*.svg are written by scripts/make_icon.py from gui/logo.py."""
    from pathlib import Path

    from emu32.gui.logo import banner_svg, logo_svg

    images = Path(__file__).parent.parent / "docs" / "images"
    assert (images / "logo.svg").read_text(encoding="utf-8") == logo_svg()
    assert (images / "banner-light.svg").read_text(encoding="utf-8") == banner_svg("light")
    assert (images / "banner-dark.svg").read_text(encoding="utf-8") == banner_svg("dark")
