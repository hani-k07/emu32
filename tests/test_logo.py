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
