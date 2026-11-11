from emu32.gui.editor_window import EditorWindow


def test_editor_window_opens(qtbot):
    window = EditorWindow()
    qtbot.addWidget(window)
    window.show()
    assert window.isVisible()
    assert window.windowTitle().startswith("emu32")
