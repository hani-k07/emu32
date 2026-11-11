"""Number conversion and integer expressions for the Converter and Calculator tools.

No Qt here, so the logic is tested directly.
"""

from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass

BASES = {"bin": 2, "oct": 8, "dec": 10, "hex": 16}

_NUMBER = re.compile(
    r"(?<![\w.])(?:0x([0-9a-f]+)|0b([01]+)|0o([0-7]+)|([0-9][0-9a-f]*)h|([01]+)b|([0-7]+)[oq]|(\d+)d?)(?![\w.])",
    re.IGNORECASE,
)
_WORDS = {"and": "&", "or": "|", "xor": "^", "not": "~", "shl": "<<", "shr": ">>", "mod": "%"}
_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.BitAnd: operator.and_,
    ast.BitOr: operator.or_,
    ast.BitXor: operator.xor,
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
}
_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Invert: operator.invert}


class NumberError(ValueError):
    pass


@dataclass(frozen=True)
class Views:
    """One value seen in every base, at a given width in bits."""

    bits: int
    unsigned: int
    signed: int
    binary: str
    octal: str
    hexadecimal: str


def views(value: int, bits: int) -> Views:
    """Wrap value to `bits` (two's complement) and show it in every base."""
    mask = (1 << bits) - 1
    unsigned = value & mask
    signed = unsigned - (1 << bits) if unsigned >> (bits - 1) else unsigned
    binary = f"{unsigned:0{bits}b}"
    grouped = " ".join(binary[i : i + 4] for i in range(0, bits, 4))
    return Views(bits, unsigned, signed, grouped, f"{unsigned:o}", f"{unsigned:0{bits // 4}X}")


def parse(text: str, base: int) -> int:
    """Read a number typed in `base`. A leading minus sign is allowed."""
    text = text.strip().replace(" ", "").replace("_", "")
    negative = text.startswith("-")
    digits = text[1:] if negative else text
    if base == 16:
        digits = re.sub(r"^0x|h$", "", digits, flags=re.IGNORECASE)
    elif base == 2:
        digits = re.sub(r"^0b|b$", "", digits, flags=re.IGNORECASE)
    elif base == 8:
        digits = re.sub(r"^0o|[oq]$", "", digits, flags=re.IGNORECASE)
    try:
        value = int(digits, base)
    except ValueError:
        raise NumberError(f"'{text}' is not a base-{base} number") from None
    return -value if negative else value


def fits(value: int, bits: int) -> bool:
    """True if value fits in `bits` as either a signed or an unsigned number."""
    return -(1 << (bits - 1)) <= value < (1 << bits)


def calculate(expression: str) -> int:
    """Evaluate an integer expression.

    Numbers: 255, 0FFh, 0xFF, 11111111b, 0b1111, 377o, 0o377. Operators: + - * / mod
    and & or | xor ^ not ~ shl << shr >>, and parentheses. Division rounds toward minus
    infinity, as Python does; use it on positive numbers for the usual result.
    """
    text = expression.strip()
    if not text:
        raise NumberError("type an expression, for example 0FFh + 1")
    text = _NUMBER.sub(_to_decimal, text)
    text = re.sub(r"\b(and|or|xor|not|shl|shr|mod)\b", lambda m: _WORDS[m.group(1).lower()], text,
                  flags=re.IGNORECASE)  # fmt: skip
    text = text.replace("//", "/").replace("/", "//")
    try:
        tree = ast.parse(text, mode="eval")
        return _eval(tree.body)
    except ZeroDivisionError:
        raise NumberError("division by zero") from None
    except (SyntaxError, NumberError, ValueError):
        raise NumberError(f"cannot read '{expression}'") from None


def _to_decimal(match: re.Match) -> str:
    hex_x, bin_b, oct_o, hex_h, bin_suffix, oct_suffix, dec = match.groups()
    for digits, base in ((hex_x, 16), (bin_b, 2), (oct_o, 8), (hex_h, 16), (bin_suffix, 2),
                         (oct_suffix, 8), (dec, 10)):  # fmt: skip
        if digits is not None:
            return str(int(digits, base))
    return match.group(0)


def _eval(node: ast.AST) -> int:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        right = _eval(node.right)
        if isinstance(node.op, ast.LShift | ast.RShift) and not 0 <= right <= 64:
            raise NumberError("shift count must be 0 to 64")
        return _BINARY[type(node.op)](_eval(node.left), right)
    raise NumberError("not an integer expression")
