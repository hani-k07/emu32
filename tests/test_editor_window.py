from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QFileDialog, QMessageBox

from emu32.gui import errors, settings, theme
from emu32.gui.dialogs import NewFileDialog, WelcomeDialog
from emu32.gui.editor_window import EditorWindow
from emu32.gui.templates import TEMPLATES
from emu32.session import Session

GOOD = ".code\nmain PROC\n    mov eax, 5\n    add eax, 3\n    ret\nmain ENDP\nEND main\n"
BAD = ".code\nmain PROC\n    mov eax, 5\n    foo eax\n    mov ebx, nowhere\n    ret\nmain ENDP\n"


def quiet_window(qtbot, monkeypatch):
    """A window whose unsaved-changes prompt answers Discard, because pytest-qt closes
    widgets before fixtures are torn down and a real prompt would wait forever."""
    win = EditorWindow()
    monkeypatch.setattr(win, "ask_unsaved", lambda doc: QMessageBox.Discard)
    qtbot.addWidget(win)
    win.show()
    return win


@pytest.fixture
def window(qtbot, monkeypatch):
    return quiet_window(qtbot, monkeypatch)


def test_menus_and_toolbar(window):
    titles = [a.text().replace("&", "") for a in window.menuBar().actions()]
    assert titles == [
        "File", "Edit", "Bookmarks", "Assembler", "Emulator", "Math", "ASCII codes", "Help",
    ]  # fmt: skip
    toolbar = window.findChild(type(window.addToolBar("x")), "main_toolbar")
    labels = [a.iconText() for a in toolbar.actions() if a.iconText()]
    for label in ("New", "Open", "Compile", "Emulate", "Calculator", "Converter", "Options",
                  "Help", "About"):  # fmt: skip
        assert label in labels
    assert "Examples" in [
        w.text() for w in toolbar.findChildren(type(toolbar.widgetForAction(toolbar.actions()[0])))
    ]


def test_compile_success_reports_size_and_instructions(window):
    window.add_document(GOOD)
    program = window.compile()
    assert program is not None
    text = window.messages.item(0).text()
    assert f"{len(program.code)} bytes of code" in text and "3 instructions" in text


def test_compile_errors_are_listed_and_jump_to_the_line(window, qtbot):
    doc = window.add_document(BAD)
    assert window.compile() is None
    items = [window.messages.item(i) for i in range(window.messages.count())]
    assert [i.text() for i in items] == [
        "line 4: unknown instruction 'foo'",
        "line 5: unknown name 'nowhere'",
    ]
    assert doc.error_lines == {4, 5}
    doc.go_to_line(1)
    rect = window.messages.visualItemRect(items[1])
    qtbot.mouseClick(window.messages.viewport(), Qt.LeftButton, pos=rect.center())
    assert doc.current_line() == 5
    doc.setPlainText(GOOD)
    window.compile()
    assert doc.error_lines == set()


def test_save_and_open_with_unusual_paths(window, tmp_path, monkeypatch):
    folder = tmp_path / "my files" / "\u00fcbung"
    folder.mkdir(parents=True)
    target = folder / "erste \u00dcbung.asm"
    text = "; Gr\u00fc\u00dfe\n" + GOOD
    doc = window.add_document(text)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(target), ""))
    assert window.save()
    assert target.read_text(encoding="utf-8").replace("\r\n", "\n") == text
    assert not doc.document().isModified()
    assert settings.recent_files() == [str(target.resolve())]
    assert window.recent_menu.actions()[0].text().endswith(str(target.resolve()))

    window.close_tab(doc)
    opened = window.open_file(target)
    assert opened.toPlainText() == text
    assert window.open_file(target) is opened  # already open: same tab
    assert window.tabs.count() == 1


def test_non_utf8_files_still_open(window, tmp_path):
    path = tmp_path / "old.asm"
    path.write_bytes("; caf\u00e9\n".encode("cp1252") + GOOD.encode())
    doc = window.open_file(path)
    assert doc.toPlainText().startswith("; caf\u00e9")
    assert "Windows-1252" in window.statusBar().currentMessage()


def test_unsaved_changes_prompt(window, monkeypatch):
    doc = window.add_document(GOOD)
    doc.insertPlainText("; edit\n")
    monkeypatch.setattr(window, "ask_unsaved", lambda d: QMessageBox.Cancel)
    assert not window.close_tab(doc)
    assert window.tabs.count() == 1
    assert not window.close()
    monkeypatch.setattr(window, "ask_unsaved", lambda d: QMessageBox.Discard)
    assert window.close_tab(doc)
    assert window.tabs.count() == 0


def test_autosave_restores_work_after_a_crash(window, qtbot, monkeypatch, tmp_path):
    path = tmp_path / "work.asm"
    path.write_text(GOOD, encoding="utf-8")
    doc = window.open_file(path)
    doc.insertPlainText("; not saved yet\n")
    window.add_document("; untouched")  # unmodified tabs are not autosaved
    window.autosave()

    # A second window starts as if the first one had crashed.
    second = quiet_window(qtbot, monkeypatch)
    monkeypatch.setattr(second, "ask_restore", lambda count: count == 1)
    assert second.restore_autosave() == 1
    restored = second.documents()[0]
    assert restored.toPlainText() == doc.toPlainText()
    assert restored.path == path.resolve()
    assert restored.document().isModified()


def test_clean_close_removes_autosave(window):
    window.add_document(GOOD).insertPlainText(";x\n")
    window.autosave()
    assert list(window.autosave_dir().glob("*.asm"))
    window.current().document().setModified(False)
    assert window.close()
    assert not list(window.autosave_dir().glob("*"))


@pytest.mark.parametrize(("key", "intel"), list(TEMPLATES))
def test_every_template_assembles(key, intel):
    Session().compile(TEMPLATES[(key, intel)], intel_syntax=intel)


def test_new_file_dialog(qtbot):
    dialog = NewFileDialog()
    qtbot.addWidget(dialog)
    dialog.findChild(type(dialog.group.buttons()[0]), "library").setChecked(True)
    dialog.intel.setChecked(True)
    assert dialog.template_key() == "library"
    assert dialog.source() == TEMPLATES[("library", True)]


def test_welcome_dialog_choices(qtbot):
    dialog = WelcomeDialog(["C:/a.asm"], show_at_start=True)
    qtbot.addWidget(dialog)
    dialog._pick("recent")
    assert not dialog.recent_list.isHidden()
    dialog._pick("examples")
    assert dialog.choice == "examples"
    assert dialog.show_at_start.isChecked()


def test_examples_open_and_compile(window):
    names = [a.text() for a in window.examples_menu.actions()]
    assert "sum array" in names
    window.examples_menu.actions()[names.index("sum array")].trigger()
    assert window.current().title == "sum_array.asm"
    assert window.compile() is not None


def test_breakpoints_and_bookmarks_follow_their_lines(window):
    doc = window.add_document(GOOD)
    doc.toggle_breakpoint(3)
    doc.toggle_bookmark(4)
    cursor = doc.textCursor()
    cursor.movePosition(cursor.MoveOperation.Start)
    cursor.insertText("; new first line\n")
    assert doc.breakpoint_lines() == [4]
    assert doc.bookmark_lines() == [5]
    doc.go_to_line(1)
    doc.next_bookmark()
    assert doc.current_line() == 5
    doc.toggle_bookmark(2)
    doc.next_bookmark(backwards=True)
    assert doc.current_line() == 2


def test_find_and_replace_all_is_one_undo_step(window):
    doc = window.add_document(GOOD)
    window.find_dialog.editor = doc
    window.find_dialog.find_text.setText("EAX")
    window.find_dialog.replace_text.setText("ecx")
    assert window.find_dialog.replace_all() == 2
    assert "eax" not in doc.toPlainText()
    doc.undo()
    assert doc.toPlainText() == GOOD


def test_zoom_changes_and_remembers_font_size(window):
    doc = window.add_document(GOOD)
    size = doc.font().pointSize()
    window.zoom(2)
    assert doc.font().pointSize() == size + 2
    assert settings.get_int("font_size", 0) == size + 2


def test_theme_switch_at_run_time(window):
    from PySide6.QtWidgets import QApplication

    doc = window.add_document(GOOD)
    for name in ("light", "dark"):
        window.switch_theme(name)
        assert theme.current_name() == name
        assert theme.token("bg.base") in QApplication.instance().styleSheet()
        background = QApplication.instance().palette().color(QPalette.Base).name().upper()
        assert background == theme.token("bg.base").upper()
        assert doc.highlighter.formats["comment"].foreground().color() == theme.color("syn.comment")
    assert window.act["compile"].icon().pixmap(16, 16).toImage() is not None


def test_light_is_the_default_theme():
    """Bright by default for classrooms; dark stays a choice in Options."""
    assert theme.DEFAULT_THEME == "light"
    theme.apply("no-such-theme")
    assert theme.current_name() == "light"


def test_unexpected_errors_go_to_the_log(monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "exec", lambda box: shown.append(box.text()))
    try:
        raise RuntimeError("boom")
    except RuntimeError as error:
        errors.report_exception(None, error)
    assert "Something went wrong" in shown[0]
    log = Path(errors.log_path()).read_text(encoding="utf-8")
    assert "RuntimeError: boom" in log and "Traceback" in log


def test_blank_start_document_gives_way_to_the_first_real_one(window, tmp_path):
    window.add_document("")
    path = tmp_path / "prog.asm"
    path.write_text("mov eax, 1\n", encoding="utf-8")
    window.open_file(path)
    assert [d.display_name() for d in window.documents()] == ["prog.asm"]
    window.add_document("")
    window.current().insertPlainText("x")
    window.add_document("")  # a blank document with typing in it stays
    assert len(window.documents()) == 3


def test_toolbar_icons_follow_the_theme(window):
    window.switch_theme("dark")
    before = window.act["save"].icon().cacheKey()
    window.switch_theme("light")
    assert window.act["save"].icon().cacheKey() != before
    window.switch_theme("dark")
