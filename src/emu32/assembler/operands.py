"""Expression evaluation and operand rewriting.

MASM style infers memory operand size from the variable: `mov eax, total` becomes
`mov eax, dword ptr [0x500004]`. Intel/NASM style treats a variable name as its address.
"""

from __future__ import annotations

import ast
import operator
import re
from dataclasses import dataclass, field

from emu32.assembler.cleaner import map_unquoted
from emu32.assembler.errors import AsmError

NAME = r"[a-z_@?][\w@?$]*"
_NAME_RE = re.compile(rf"(?<![\w@?$.]){NAME}")
_OPERATOR_RE = re.compile(rf"(?<![\w@?$])(offset|sizeof|lengthof|type)\s+({NAME})")
_LOCATION_RE = re.compile(r"(?<![\w@?$])\$(?![\w@?$])")
_QUOTED_RE = re.compile(r"'([^']*)'|\"([^\"]*)\"")
_PTR_RE = re.compile(r"^(byte|sbyte|word|sword|dword|sdword|qword|tbyte)\s+ptr\s+(.*)$")
_SIGNED_PTR_RE = re.compile(r"\bs(byte|word|dword)\s+ptr\b")

REGISTER_BITS = {
    **dict.fromkeys(("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp", "esp"), 32),
    **dict.fromkeys(("ax", "bx", "cx", "dx", "si", "di", "bp", "sp"), 16),
    **dict.fromkeys(("al", "ah", "bl", "bh", "cl", "ch", "dl", "dh"), 8),
    **dict.fromkeys(("cs", "ds", "es", "fs", "gs", "ss"), 16),
}
SIZE_NAMES = {1: "byte", 2: "word", 4: "dword", 8: "qword", 10: "tbyte"}
_REAL_PTR_RE = re.compile(r"\b(real4|real8|real10)\s+ptr\b")
_REAL_SIZE = {"real4": "dword", "real8": "qword", "real10": "tbyte"}
KEYWORDS = frozenset(REGISTER_BITS) | {
    "ptr", "byte", "word", "dword", "qword", "tbyte", "real4", "real8", "real10", "short",
    "near", "far",
}  # fmt: skip

_BINARY_OPS = {
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
# MASM's word operators in constant expressions, as Python operators.
_WORD_OPERATORS = {
    "and": "&", "or": "|", "xor": "^", "not": "~", "shl": "<<", "shr": ">>",
    "eq": "==", "ne": "!=", "lt": "<", "le": "<=", "gt": ">", "ge": ">=",
}  # fmt: skip
_WORD_OPERATOR_RE = re.compile(r"(?<![\w@?$])(and|or|xor|not|shl|shr|eq|ne|lt|le|gt|ge)(?![\w@?$])")
_COMPARE_OPS = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
    ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
}  # fmt: skip


@dataclass(frozen=True)
class Symbol:
    """A variable in the data section."""

    name: str
    address: int
    size: int  # bytes per element
    count: int  # elements on the defining line (LENGTHOF)
    signed: bool = False
    kind: str = ""  # the STRUCT name, for a structure variable

    @property
    def type_name(self) -> str:
        if self.kind:
            return self.kind
        return ("s" if self.signed else "") + SIZE_NAMES.get(self.size, f"{self.size}-byte")


@dataclass
class Scope:
    constants: dict[str, int] = field(default_factory=dict)
    symbols: dict[str, Symbol] = field(default_factory=dict)
    # Names that resolve to a fixed address, such as library routines (added in M3).
    externals: dict[str, int] = field(default_factory=dict)


def names_in(text: str) -> list[str]:
    found: list[str] = []
    map_unquoted(text, lambda part: found.extend(_NAME_RE.findall(part)) or part)
    return found


def split_operands(text: str) -> list[str]:
    """Split on commas that are not inside quotes, brackets or parentheses."""
    parts, depth, quote, current = [], 0, None, []
    for char in text:
        if quote:
            quote = None if char == quote else quote
        elif char in "'\"":
            quote = char
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    parts.append("".join(current).strip())
    return [part for part in parts if part] if any(parts) else []


def substitute_names(text: str, values: dict[str, int]) -> str:
    def replace(part: str) -> str:
        return _NAME_RE.sub(
            lambda m: hex(values[m.group(0)]) if m.group(0) in values else m.group(0), part
        )

    return map_unquoted(text, replace)


def apply_operators(text: str, scope: Scope) -> str:
    def replace(match: re.Match) -> str:
        op, name = match.groups()
        symbol = scope.symbols.get(name)
        if symbol is None:
            if op == "offset" and name in scope.externals:
                return hex(scope.externals[name])
            if op == "offset":
                return name  # a code label; Keystone resolves it
            raise AsmError(f"{op.upper()} needs a variable name, and '{name}' is not one")
        if op == "offset":
            return hex(symbol.address)
        if op == "type":
            return hex(symbol.size)
        if op == "lengthof":
            return hex(symbol.count)
        return hex(symbol.count * symbol.size)

    return map_unquoted(text, lambda part: _OPERATOR_RE.sub(replace, part))


def _char_value(match: re.Match) -> str:
    text = match.group(1) if match.group(1) is not None else match.group(2)
    if not text:
        raise AsmError("empty character constant")
    if not text.isascii() or len(text) > 4:
        raise AsmError(f"'{text}' is not a valid character constant")
    return hex(int.from_bytes(text.encode("ascii"), "big"))


def evaluate(text: str, scope: Scope, here: int) -> int:
    """Evaluate a constant expression. Variables stand for their address."""
    expr = apply_operators(text, scope)
    expr = _QUOTED_RE.sub(_char_value, expr)
    expr = _LOCATION_RE.sub(hex(here), expr)
    values = {**scope.constants, **{n: s.address for n, s in scope.symbols.items()}}
    expr = substitute_names(expr, values)
    leftover = [n for n in names_in(expr) if not re.fullmatch(r"x[0-9a-f]+", n)]
    if "mod" in leftover:
        expr = re.sub(r"\bmod\b", "%", expr)
        leftover.remove("mod")
    if set(leftover) & _WORD_OPERATORS.keys():
        expr = _WORD_OPERATOR_RE.sub(lambda m: f" {_WORD_OPERATORS[m.group(1)]} ", expr)
        leftover = [n for n in leftover if n not in _WORD_OPERATORS]
    if leftover:
        raise AsmError(f"unknown name '{leftover[0]}'")
    expr = re.sub(r"(?<![\w.])0+(?=\d)", "", expr).replace("/", "//").strip()
    try:
        return _eval(ast.parse(expr, mode="eval").body)
    except (SyntaxError, AsmError):
        raise AsmError(f"invalid expression '{text}'") from None
    except ZeroDivisionError:
        raise AsmError(f"division by zero in '{text}'") from None


def _eval(node: ast.AST) -> int:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd | ast.Invert):
        value = _eval(node.operand)
        if isinstance(node.op, ast.Invert):
            return ~value
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _COMPARE_OPS:
        # MASM's EQ, NE, LT, ... give -1 (all bits set) for true and 0 for false.
        holds = _COMPARE_OPS[type(node.ops[0])](_eval(node.left), _eval(node.comparators[0]))
        return -1 if holds else 0
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPS:
        return _BINARY_OPS[type(node.op)](_eval(node.left), _eval(node.right))
    raise AsmError("invalid expression")


def rewrite_operand(text: str, scope: Scope, nasm: bool) -> str:
    """Turn one source operand into text Keystone understands."""
    op = apply_operators(text, scope)
    op = _REAL_PTR_RE.sub(lambda m: f"{_REAL_SIZE[m.group(1)]} ptr", op)
    if "[" not in op and set(names_in(op)) & _WORD_OPERATORS.keys():
        # `1 SHL 4` or `MASK AND 0Fh` as an immediate: work it out here.
        return hex(evaluate(op, scope, 0) & 0xFFFFFFFF)
    op = substitute_names(op, scope.constants)
    op = _QUOTED_RE.sub(_char_value, op)
    op = _SIGNED_PTR_RE.sub(lambda m: f"{m.group(1)} ptr", op)
    op = substitute_names(op, scope.externals)
    used = [name for name in names_in(op) if name in scope.symbols]
    if not used:
        return op
    addresses = {name: scope.symbols[name].address for name in used}
    if nasm:
        return substitute_names(op, addresses)
    match = _PTR_RE.match(op)
    size_word, body = (match.group(1), match.group(2)) if match else (None, op)
    pieces = [piece.strip() for piece in re.split(r"[\[\]]", body) if piece.strip()]
    expr = substitute_names("+".join(pieces), addresses)
    expr = re.sub(r"\+\s*-", "-", re.sub(r"\+\s*\+", "+", expr))
    size_word = size_word or SIZE_NAMES.get(scope.symbols[used[0]].size)
    return f"{size_word} ptr [{expr}]" if size_word else f"[{expr}]"
