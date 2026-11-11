"""First pass: strip comments, lowercase everything outside strings, rewrite number formats."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from emu32.assembler.errors import AsmMessage

_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
# 0Ah, 1010b, 12d, 10. Hex must start with a digit, as in MASM, so `ah` and `bh` stay
# registers. Plain decimals are converted too, so a leading zero never means octal.
_SUFFIX_NUMBER = re.compile(
    r"(?<![\w@?$.])(?:([0-9][0-9a-f]*)h|([01]+)b|([0-9]+)d|([0-9]+))(?![\w@?$])"
)


@dataclass(frozen=True)
class SourceLine:
    number: int
    text: str


def map_unquoted(text: str, fn: Callable[[str], str]) -> str:
    """Apply fn to the parts of text that are not inside quotes."""
    out, last = [], 0
    for match in _QUOTED.finditer(text):
        out.append(fn(text[last : match.start()]))
        out.append(match.group(0))
        last = match.end()
    out.append(fn(text[last:]))
    return "".join(out)


def _strip_comment(text: str) -> str:
    quote = None
    for index, char in enumerate(text):
        if quote:
            if char == quote:
                quote = None
        elif char in "'\"":
            quote = char
        elif char == ";":
            return text[:index]
    if quote:
        raise ValueError("a string is missing its closing quote")
    return text


def _convert_numbers(text: str) -> str:
    def to_hex(match: re.Match) -> str:
        hex_digits, binary, decimal, plain = match.groups()
        if hex_digits is not None:
            return hex(int(hex_digits, 16))
        if binary is not None:
            return hex(int(binary, 2))
        return hex(int(decimal or plain, 10))

    return _SUFFIX_NUMBER.sub(to_hex, text)


def clean(source: str) -> tuple[list[SourceLine], list[AsmMessage]]:
    lines, errors = [], []
    for number, raw in enumerate(source.splitlines(), start=1):
        try:
            text = _strip_comment(raw).strip()
        except ValueError as error:
            errors.append(AsmMessage(number, str(error)))
            continue
        if text:
            text = map_unquoted(
                text, lambda part: re.sub(r"\s+", " ", _convert_numbers(part.lower()))
            )
            lines.append(SourceLine(number, text))
    return lines, errors
