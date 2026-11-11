"""Fail if the repository breaks its attribution, style or hygiene rules.

Usage:
    python scripts/check_repo_rules.py                    tracked files and all commit messages
    python scripts/check_repo_rules.py --commit-msg FILE  one commit message (used by the hook)

Only the standard library is used, so the git hook works without the venv.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Attribution strings. "AI" is matched case-sensitively so words like "said" pass.
FORBIDDEN_TEXT = re.compile(
    r"co-authored-by|generated with|\bclaude\b|anthropic|\bchatgpt\b|\bopenai\b"
    r"|\bcopilot\b|(?-i:\bAI\b)",
    re.IGNORECASE,
)
EMOJI = re.compile("[\U0001f000-\U0001faff\u2600-\u27bf\u2b00-\u2bff\ufe0f\u200d]")
SECRET_TEXT = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{30,}|\bAKIA[0-9A-Z]{16}\b"
)

# Mirrors the assistant, local-only and secret groups in .gitignore.
BLOCKED_PATHS = [
    "CLAUDE.md",
    "CLAUDE.local.md",
    ".claude/",
    "AGENTS.md",
    "GEMINI.md",
    ".cursor/",
    ".cursorrules",
    ".windsurf/",
    ".continue/",
    ".aider*",
    ".github/copilot-instructions.md",
    "EMU32-PROMPT.md",
    "PROMPT*.md",
    "*.local.md",
    "docs/reference/",
    "plans/",
    "notes/",
    "scratch/",
    "TODO.local*",
    "docs/observations/*.png",
    "docs/observations/*.jpg",
    "docs/observations/*.jpeg",
    "docs/observations/*.gif",
    "docs/observations/*.bmp",
    "docs/observations/*.webp",
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.pfx",
    "secrets/",
]

# These files must name the forbidden strings in order to block them.
CONTENT_EXEMPT = {".gitignore", "scripts/check_repo_rules.py", "tests/test_repo_rules.py"}


def path_blocked(path: str) -> bool:
    parts = path.split("/")
    for pattern in BLOCKED_PATHS:
        if pattern.endswith("/"):
            directory = pattern.rstrip("/")
            if "/" in directory:
                if path.startswith(directory + "/"):
                    return True
            elif directory in parts[:-1]:
                return True
        elif "/" in pattern:
            if fnmatch.fnmatchcase(path, pattern):
                return True
        elif fnmatch.fnmatchcase(parts[-1], pattern):
            return True
    return False


def text_problems(text: str) -> list[tuple[int, str]]:
    problems = []
    for number, line in enumerate(text.splitlines(), start=1):
        if match := FORBIDDEN_TEXT.search(line):
            problems.append((number, f"forbidden text {match.group(0)!r}"))
        if EMOJI.search(line):
            problems.append((number, "emoji"))
        if SECRET_TEXT.search(line):
            problems.append((number, "possible secret"))
    return problems


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout


def check_tree() -> list[str]:
    errors = []
    for path in git("ls-files").splitlines():
        if path_blocked(path):
            errors.append(f"{path}: must not be tracked")
            continue
        if path in CONTENT_EXEMPT:
            continue
        try:
            text = (ROOT / path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        errors += [f"{path}:{n}: {why}" for n, why in text_problems(text)]
    for entry in git("log", "--format=%h%x01%B%x00").split("\0"):
        if not entry.strip():
            continue
        sha, _, message = entry.strip().partition("\x01")
        errors += [f"commit {sha} line {n}: {why}" for n, why in text_problems(message)]
    return errors


def check_message(path: str) -> list[str]:
    text = Path(path).read_text(encoding="utf-8")
    # Lines starting with '#' are git's template comments and never reach the commit.
    body = "\n".join("" if line.startswith("#") else line for line in text.splitlines())
    return [f"commit message line {n}: {why}" for n, why in text_problems(body)]


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "--commit-msg":
        errors = check_message(argv[1])
    elif not argv:
        errors = check_tree()
    else:
        print(__doc__)
        return 2
    for error in errors:
        print(error)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
