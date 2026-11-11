"""User settings, recent files and the app-data folder (log file, autosave)."""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

RECENT_LIMIT = 10


def app_data_dir() -> Path:
    """Per-user folder for settings, the log and autosave files.

    EMU32_HOME overrides it (tests, and the portable build in a later milestone).
    """
    override = os.environ.get("EMU32_HOME")
    base = override or QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)
    path = Path(base) if base else Path.home() / ".emu32"
    if not override and path.name.lower() != "emu32":
        path = path / "emu32"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings() -> QSettings:
    return QSettings(str(app_data_dir() / "settings.ini"), QSettings.IniFormat)


def get_bool(key: str, default: bool) -> bool:
    value = settings().value(key, default)
    return value if isinstance(value, bool) else str(value).lower() == "true"


def get_int(key: str, default: int) -> int:
    try:
        return int(settings().value(key, default))
    except (TypeError, ValueError):
        return default


def get_str(key: str, default: str) -> str:
    return str(settings().value(key, default))


def put(key: str, value: object) -> None:
    store = settings()
    store.setValue(key, value)
    store.sync()


def recent_files() -> list[str]:
    value = settings().value("recent_files", [])
    files = [value] if isinstance(value, str) else list(value or [])
    return [f for f in files if f]


def add_recent_file(path: str) -> list[str]:
    files = [path, *(f for f in recent_files() if f != path)][:RECENT_LIMIT]
    put("recent_files", files)
    return files


PORTABLE_MARKER = "portable.txt"


def use_portable_home(program_dir: Path) -> bool:
    """In the portable build, keep settings, log and autosave next to the program.

    The release's portable folder has a `portable.txt` marker. If that folder cannot be
    written (a read-only network share), the normal app-data folder is used instead.
    """
    if "EMU32_HOME" in os.environ or not (program_dir / PORTABLE_MARKER).exists():
        return False
    home = program_dir / "data"
    try:
        home.mkdir(exist_ok=True)
        probe = home / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        return False
    os.environ["EMU32_HOME"] = str(home)
    return True
