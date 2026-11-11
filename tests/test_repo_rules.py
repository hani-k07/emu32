import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "check_repo_rules", Path(__file__).parent.parent / "scripts" / "check_repo_rules.py"
)
rules = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rules)


def test_attribution_lines_are_rejected():
    assert rules.text_problems("fix: x\n\nCo-Authored-By: Someone <a@b.c>")
    assert rules.text_problems("Generated with some tool")
    assert rules.text_problems("written by Claude")
    assert rules.text_problems("an AI wrote this")


def test_ordinary_text_passes():
    assert rules.text_problems("feat: add said, aim and tail handling\n\nPlain text.") == []


def test_emoji_and_secrets_are_rejected():
    assert rules.text_problems("done \U0001f680")
    assert rules.text_problems("-----BEGIN RSA PRIVATE KEY-----")


def test_blocked_paths():
    for path in [
        "CLAUDE.md",
        ".claude/settings.json",
        "docs/reference/shot.png",
        "docs/observations/screen.png",
        "docs/observations/run1/regs.jpg",
        "EMU32-PROMPT.md",
        "PROMPT-v2.md",
        "a/b/notes.local.md",
        ".env",
        ".env.prod",
        "certs/x.pem",
        "secrets/token.txt",
        ".github/copilot-instructions.md",
    ]:
        assert rules.path_blocked(path), path


def test_allowed_paths():
    for path in [
        "src/emu32/__main__.py",
        "packaging/emu32.spec",
        "docs/decisions.md",
        "README.md",
        ".github/workflows/ci.yml",
        ".gitignore",
    ]:
        assert not rules.path_blocked(path), path
