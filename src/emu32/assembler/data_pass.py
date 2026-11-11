"""Packs data definitions into bytes and records each variable in the symbol table."""

from __future__ import annotations

import math
import re
import struct

from emu32.assembler.errors import AsmError
from emu32.assembler.operands import SIZE_NAMES, Scope, Symbol, evaluate, split_operands

DATA_SIZES = {
    "db": 1, "byte": 1, "sbyte": 1,
    "dw": 2, "word": 2, "sword": 2,
    "dd": 4, "dword": 4, "sdword": 4,
    "dq": 8, "qword": 8,
    "real4": 4, "real8": 8, "real10": 10, "dt": 10, "tbyte": 10,
}  # fmt: skip
FLOATS = {"real4", "real8", "real10"}
RESERVE_SIZES = {"resb": 1, "resw": 2, "resd": 4}
SIGNED = {"sbyte", "sword", "sdword"}
UNSUPPORTED_DATA = {}

_DUP_RE = re.compile(r"(.+?)\s*dup\s*\((.*)\)")


class DataBuilder:
    def __init__(self, base: int, limit: int, scope: Scope) -> None:
        self.base = base
        self.limit = limit
        self.scope = scope
        self.data = bytearray()
        self.spans: dict[int, tuple[int, int]] = {}  # source line -> (address, size)

    @property
    def here(self) -> int:
        return self.base + len(self.data)

    def define(self, line: int, name: str | None, directive: str, operands: str) -> None:
        start = self.here
        blob = bytearray()
        if directive in RESERVE_SIZES:
            size = RESERVE_SIZES[directive]
            count = evaluate(operands, self.scope, start)
            if count < 0:
                raise AsmError(f"cannot reserve {count} items")
            blob += bytes(size * count)
        else:
            size = DATA_SIZES[directive]
            items = split_operands(operands)
            if not items:
                raise AsmError("missing value; use ? for an uninitialized value")
            floating = directive in FLOATS
            count = sum(self._item(item, size, blob, start, floating) for item in items)
        if len(self.data) + len(blob) > self.limit:
            raise AsmError(f"the data section is larger than {self.limit} bytes")
        self.data += blob
        self.spans[line] = (start, len(blob))
        if name:
            kind = directive if directive in FLOATS else ""
            self.scope.symbols[name] = Symbol(name, start, size, count, directive in SIGNED, kind)

    def define_raw(
        self, line: int, name: str | None, blob: bytes, size: int, count: int, kind: str = ""
    ) -> None:
        """Bytes built elsewhere (a STRUCT variable, ALIGN padding)."""
        start = self.here
        if len(self.data) + len(blob) > self.limit:
            raise AsmError(f"the data section is larger than {self.limit} bytes")
        self.data += blob
        if line:
            self.spans[line] = (start, len(blob))
        if name:
            self.scope.symbols[name] = Symbol(name, start, size, count, False, kind)

    def _item(
        self, item: str, size: int, out: bytearray, start: int, floating: bool = False
    ) -> int:
        """Append one initializer to out and return how many elements it holds."""
        dup = _DUP_RE.fullmatch(item)
        if dup:
            times = evaluate(dup.group(1), self.scope, start + len(out))
            if times < 0:
                raise AsmError(f"DUP count {times} is negative")
            inner = bytearray()
            elements = sum(
                self._item(part, size, inner, start, floating)
                for part in split_operands(dup.group(2))
            )
            out += inner * times
            return elements * times
        if item == "?":
            out += bytes(size)
            return 1
        if floating:
            out += pack_real(self._real(item, start + len(out)), size)
            return 1
        if size == 1 and len(item) >= 2 and item[0] == item[-1] and item[0] in "'\"":
            text = item[1:-1]
            if item[0] in text:
                raise AsmError(
                    "doubled quotes inside a string are not supported; "
                    'use the other quote character, as in "it\'s"'
                )
            if not text.isascii():
                raise AsmError("strings may contain ASCII characters only")
            out += text.encode("ascii")
            return len(text)
        if re.fullmatch(r"-?[0-9]+\.[0-9]*(?:e[+-]?[0-9]+)?", item):
            raise AsmError(f"{item} is a floating-point number; declare it as REAL4 or REAL8")
        value = evaluate(item, self.scope, start + len(out))
        bits = size * 8
        if not -(1 << (bits - 1)) <= value < (1 << bits):
            raise AsmError(f"value {value} does not fit in a {SIZE_NAMES[size]}")
        out += (value & ((1 << bits) - 1)).to_bytes(size, "little")
        return 1

    def _real(self, item: str, here: int) -> float:
        try:
            return float(item)
        except ValueError:
            return float(evaluate(item, self.scope, here))  # an integer expression


def pack_real(value: float, size: int) -> bytes:
    """IEEE single (4 bytes), double (8) or x87 extended precision (10), little-endian."""
    if size == 4:
        try:
            return struct.pack("<f", value)
        except OverflowError:
            raise AsmError(f"{value} is too large for REAL4") from None
    if size == 8:
        return struct.pack("<d", value)
    sign = 0x8000 if math.copysign(1.0, value) < 0 else 0
    value = abs(value)
    if value == 0:
        return bytes(8) + sign.to_bytes(2, "little")
    if math.isinf(value):
        return (1 << 63).to_bytes(8, "little") + (sign | 0x7FFF).to_bytes(2, "little")
    fraction, exponent = math.frexp(value)  # value = fraction * 2**exponent, 0.5 <= f < 1
    mantissa = int(fraction * (1 << 64))
    return mantissa.to_bytes(8, "little") + (sign | (exponent - 1 + 16383)).to_bytes(2, "little")
