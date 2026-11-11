"""emu32 must work fully offline (section 8.8): no network code anywhere in the program."""

import ast
from pathlib import Path

SOURCE = Path(__file__).parent.parent / "src" / "emu32"
NETWORK_MODULES = {
    "socket", "ssl", "urllib", "http", "ftplib", "smtplib", "poplib", "imaplib", "xmlrpc",
    "requests", "httpx", "aiohttp", "asyncio", "PySide6.QtNetwork", "QtNetwork",
}  # fmt: skip


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found |= {f"{node.module}.{alias.name}" for alias in node.names}
    return found


def test_no_network_modules_are_imported():
    offenders = {}
    for path in SOURCE.rglob("*.py"):
        hits = {
            name
            for name in imported_modules(path)
            if any(name == m or name.startswith(m + ".") for m in NETWORK_MODULES)
        }
        if hits:
            offenders[str(path.relative_to(SOURCE))] = sorted(hits)
    # The self-test's guard imports socket only to switch networking off.
    assert offenders == {"__main__.py": ["socket"]}


def test_self_test_guard_records_and_blocks_connections(monkeypatch):
    import socket

    import pytest

    from emu32.__main__ import forbid_network

    # Register the originals so pytest puts them back after the test.
    for owner, name in ((socket.socket, "connect"), (socket.socket, "connect_ex"),
                        (socket, "create_connection"), (socket, "getaddrinfo")):  # fmt: skip
        monkeypatch.setattr(owner, name, getattr(owner, name))
    attempts = forbid_network()
    with pytest.raises(OSError, match="offline"):
        socket.create_connection(("192.0.2.1", 80), timeout=0.01)
    with pytest.raises(OSError, match="offline"):
        socket.getaddrinfo("example.org", 80)
    assert len(attempts) == 2
