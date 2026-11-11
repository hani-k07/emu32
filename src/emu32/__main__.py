import os
import sys
from pathlib import Path


def forbid_network() -> list[str]:
    """Make every network connection attempt fail, and record it. emu32 works offline, so
    the self-test fails if anything in the program tries to connect."""
    import socket

    attempts: list[str] = []

    def refuse(*args, **kwargs):
        attempts.append(repr(args[1:] if args and isinstance(args[0], socket.socket) else args))
        raise OSError("emu32 works offline; a network connection was attempted")

    socket.socket.connect = refuse
    socket.socket.connect_ex = refuse
    socket.create_connection = refuse
    socket.getaddrinfo = refuse
    return attempts


def self_test() -> int:
    """Check a built copy works without showing a window: assemble and run an example,
    create both windows offscreen. Exit code 0 means it passed (used by the release build).
    A failure is written to emu32.log in the app-data folder, since a windowed program has
    no console."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    import faulthandler
    import traceback

    from emu32.gui.errors import log_path, write_log

    # A crash in native code leaves no Python traceback; this records where it happened.
    crash_log = log_path().open("a", encoding="utf-8")
    faulthandler.enable(file=crash_log)

    attempts = forbid_network()
    try:
        from importlib import resources

        from PySide6.QtWidgets import QApplication

        from emu32.gui.editor_window import EditorWindow
        from emu32.gui.emulator_window import EmulatorWindow
        from emu32.session import Session

        example = resources.files("emu32") / "examples" / "sum_array.asm"
        source = example.read_text(encoding="utf-8")
        session = Session()
        session.load(source)
        session.run()
        output = session.console.output()
        if output != "Sum: 100\n":
            write_log(f"self-test: example printed {output!r}")
            return 1
        app = QApplication([])
        editor, emulator = EditorWindow(), EmulatorWindow()
        ok = emulator.load_source(source) and editor.act["compile"].isEnabled()
        emulator.shutdown()
        app.quit()
        if not ok:
            write_log("self-test: the windows did not load the example")
            return 1
        if attempts:
            write_log(f"self-test: network connections were attempted: {attempts}")
            return 1
        write_log("self-test: passed")
        return 0
    except Exception:  # noqa: BLE001 - every failure must end up in the log
        write_log("self-test failed:\n" + traceback.format_exc())
        return 1


def main() -> int:
    if getattr(sys, "frozen", False):
        from emu32.gui.settings import use_portable_home

        use_portable_home(Path(sys.executable).parent)
    if "--self-test" in sys.argv[1:]:
        return self_test()

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from emu32.gui import settings, theme
    from emu32.gui.editor_window import EditorWindow
    from emu32.gui.errors import install_excepthook

    app = QApplication(sys.argv)
    app.setApplicationName("emu32")
    install_excepthook()
    theme.apply(settings.get_str("theme", theme.system_theme()))
    window = EditorWindow()
    window.show()
    files = [arg for arg in sys.argv[1:] if not arg.startswith("-")]

    def start() -> None:
        restored = window.restore_autosave()
        for path in files:
            window.open_file(path)
        if not files and not restored and settings.get_bool("show_welcome", True):
            window.show_welcome()

    # After the event loop starts, so the window is on screen behind any dialog.
    QTimer.singleShot(0, start)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
