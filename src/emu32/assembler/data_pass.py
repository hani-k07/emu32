"""Packs data definitions into bytes and records each variable in the symbol table."""

from __future__ import annotations

import re

from emu32.assembler.errors import AsmError
from emu32.assembler.operands import SIZE_NAMES, Scope, Symbol, evaluate, split_operands

DATA_SIZES = {
    "db": 1, "byte": 1, "sbyte": 1,
    "dw": 2, "word": 2, "sword": 2,
    "dd": 4, "dword": 4, "sdword": 4,
    "dq": 8, "qword": 8,
}  # fmt: skip
RESERVE_SIZES = {"resb": 1, "resw": 2, "resd": 4}
SIGNED = {"sbyte", "sword", "sdword"}
UNSUPPORTED_DATA = {
    "dt": "80-bit data (dt) is not supported",
    "tbyte": "80-bit data (tbyte) is not supported",
    "real4": "floating-point data (real4) is not supported",
    "real8": "floating-point data (real8) is not supported",
}

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
            count = sum(self._item(item, size, blob, start) for item in items)
        if len(self.data) + len(blob) > self.limit:
            raise AsmError(f"the data section is larger than {self.limit} bytes")
        self.data += blob
        self.spans[line] = (start, len(blob))
        if name:
            self.scope.symbols[name] = Symbol(name, start, size, count, directive in SIGNED)

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

    def _item(self, item: str, size: int, out: bytearray, start: int) -> int:
        """Append one initializer to out and return how many elements it holds."""
        dup = _DUP_RE.fullmatch(item)
        if dup:
            times = evaluate(dup.group(1), self.scope, start + len(out))
            if times < 0:
                raise AsmError(f"DUP count {times} is negative")
            inner = bytearray()
            elements = sum(
                self._item(part, size, inner, start) for part in split_operands(dup.group(2))
            )
            out += inner * times
            return elements * times
        if item == "?":
            out += bytes(size)
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
        value = evaluate(item, self.scope, start + len(out))
        bits = size * 8
        if not -(1 << (bits - 1)) <= value < (1 << bits):
            raise AsmError(f"value {value} does not fit in a {SIZE_NAMES[size]}")
        out += (value & ((1 << bits) - 1)).to_bytes(size, "little")
        return 1
