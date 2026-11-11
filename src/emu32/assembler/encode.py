"""Assembler driver: sections and directives, code pass, line map, errors and listing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import capstone
import keystone

from emu32.assembler.cleaner import SourceLine, clean, map_unquoted
from emu32.assembler.data_pass import DATA_SIZES, RESERVE_SIZES, UNSUPPORTED_DATA, DataBuilder
from emu32.assembler.errors import AsmError, AsmMessage, AssemblyError
from emu32.assembler.masm_pre import StructField, preprocess, split_args
from emu32.assembler.operands import (
    KEYWORDS,
    NAME,
    REGISTER_BITS,
    SIZE_NAMES,
    Scope,
    Symbol,
    evaluate,
    names_in,
    rewrite_operand,
    split_operands,
    substitute_names,
)
from emu32.cpu_mode import MODE32, CpuMode

_PREFIXES = {"rep", "repe", "repz", "repne", "repnz", "lock"}
# Instructions whose operands legitimately differ in size.
_MIXED_SIZE = {"movzx", "movsx", "shl", "shr", "sar", "sal", "rol", "ror", "rcl", "rcr"}
_CONSTANT_RE = re.compile(rf"^({NAME}):?\s*(?:=|equ\b)\s*(.*)$")
_CS = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
MNEMONICS = frozenset(_CS.insn_name(i) for i in range(1, capstone.x86_const.X86_INS_ENDING))
_LABEL_RE = re.compile(rf"^({NAME})\s*::?\s*(.*)$")
_LOCAL_LABEL_RE = re.compile(rf"^(\.?{NAME})\s*:\s*(.*)$")
_LOCATION_RE = re.compile(r"(?<![\w@?$])\$(?![\w@?$])")
_CPU_DIRECTIVE_RE = re.compile(r"\.(?:[3-6]86p?|mmx|xmm)")
_HIGH_LEVEL = {
    ".if", ".elseif", ".else", ".endif", ".while", ".endw", ".repeat", ".until",
    ".untilcxz", ".break", ".continue",
}  # fmt: skip
_UNSUPPORTED_WORDS = {
    "macro": "macros are not supported",
    "endm": "macros are not supported",
    "struct": "structures are supported in MASM style only",
    "struc": "structures are supported in MASM style only",
    "ends": "ENDS without a matching STRUCT; segments are not supported",
    "segment": "segments are not supported; use .data and .code",
    "assume": "ASSUME is not needed: emu32 uses flat 32-bit memory without segments",
}
_DATA_SEGMENT_HINT = (
    "@data is a 16-bit segment value; 32-bit flat memory has no segments. "
    "Remove 'mov ax, @data' and 'mov ds, ax'"
)


@dataclass
class Program:
    code: bytes
    data: bytes
    entry: int
    symbols: dict[str, Symbol]
    constants: dict[str, int]
    labels: dict[str, int]
    address_to_line: dict[int, int]
    line_to_address: dict[int, int]
    data_spans: dict[int, tuple[int, int]]
    warnings: list[AsmMessage] = field(default_factory=list)
    mode: CpuMode = MODE32

    @property
    def instruction_count(self) -> int:
        return len(self.address_to_line)

    def listing(self, source: str) -> str:
        """Text listing: line number, address, bytes, source."""
        code_base = self.mode.region("code").start
        data_base = self.mode.region("data").start
        addresses = sorted(self.address_to_line) + [code_base + len(self.code)]
        sizes = {a: b - a for a, b in zip(addresses, addresses[1:], strict=False)}
        rows = []
        for number, text in enumerate(source.splitlines(), start=1):
            address, blob = None, b""
            if number in self.line_to_address:
                address = self.line_to_address[number]
                blob = self.code[address - code_base : address - code_base + sizes[address]]
            elif number in self.data_spans:
                address, size = self.data_spans[number]
                blob = self.data[address - data_base : address - data_base + size]
            where = self.mode.format_address(address) if address is not None else ""
            shown = blob[:8].hex(" ").upper() + (" ..." if len(blob) > 8 else "")
            rows.append(f"{number:5}  {where:8}  {shown:27}  {text}")
        return "\n".join(rows) + "\n"


@dataclass
class _Frame:
    """A PROC with USES, parameters or LOCAL variables (MASM stdcall frame)."""

    name: str
    line: int
    uses: list[str]
    params: dict[str, tuple[int, int]]  # name -> (offset from EBP, size in bytes)
    locals: dict[str, tuple[int, int]] = field(default_factory=dict)
    local_bytes: int = 0
    started: bool = False  # prologue already emitted

    @property
    def uses_ebp(self) -> bool:
        return bool(self.params or self.locals)

    @property
    def variables(self) -> dict[str, tuple[int, int]]:
        return {**self.params, **self.locals}


@dataclass
class _Item:
    line: int
    text: str
    label: bool = False
    proc: str | None = None
    frame: _Frame | None = None
    invoke: bool = False


_SIZE_OF_TYPE = {
    "byte": 1, "sbyte": 1, "word": 2, "sword": 2, "dword": 4, "sdword": 4, "qword": 8,
    "real4": 4, "real8": 8, "real10": 10,
}  # fmt: skip
_PROC_ATTRIBUTES = {"near", "far", "public", "private", "stdcall", "c", "pascal"}
_FRAME_PTR_RE = re.compile(r"^(byte|sbyte|word|sword|dword|sdword)\s+ptr\s+(.*)$")


def _ebp_offset(offset: int) -> str:
    # Generated numbers are always hex: after Keystone has run in NASM mode, its default
    # number base stays 16 for the whole process, so a plain 12 would mean 18. D62.
    return f"ebp{'+' if offset >= 0 else '-'}{hex(abs(offset))}"


class _Assembler:
    def __init__(
        self,
        mode: CpuMode,
        nasm: bool,
        externals: dict[str, int],
        structs: dict[str, list[StructField]] | None = None,
    ) -> None:
        self.structs = structs or {}
        self.layouts: dict[str, tuple[int, dict[str, tuple[int, int, int, bytes]]]] = {}
        self.struct_vars: dict[str, str] = {}  # variable -> STRUCT name
        self.mode = mode
        self.nasm = nasm
        self.scope = Scope(externals=dict(externals))
        data = mode.region("data")
        self.data = DataBuilder(data.start, data.size, self.scope)
        self.errors: list[AsmMessage] = []
        self.warnings: list[AsmMessage] = []
        self.names: dict[str, int] = {}  # every defined name -> line, to catch duplicates
        self.items: list[_Item] = []
        self.labels: list[str] = []
        self.section = "code"
        self.procs: list[tuple[str, int]] = []
        self.frame: _Frame | None = None
        self.local_labels: dict[str, set[str]] = {}  # procedure -> its own labels
        self.display: dict[str, str] = {}  # label name given to Keystone -> name shown
        self.end_name: tuple[str, int] | None = None
        self.ended = False

    # Pass 1: directives, data, constants, labels

    def first_pass(self, lines: list[SourceLine]) -> None:
        for line in lines:
            if self.ended:
                break
            try:
                self._line(line.number, line.text)
            except AsmError as error:
                self.errors.append(AsmMessage(line.number, error.text))
        for name, number in self.procs:
            self.errors.append(AsmMessage(number, f"procedure '{name}' has no ENDP"))

    def _define(self, name: str, number: int) -> None:
        if name in KEYWORDS or name in MNEMONICS:
            raise AsmError(f"'{name}' is a reserved word and cannot be used as a name")
        if name in self.names:
            raise AsmError(f"'{name}' is already defined on line {self.names[name]}")
        if name in self.scope.externals:
            raise AsmError(f"'{name}' is the name of a built-in routine")
        self.names[name] = number

    def _line(self, number: int, text: str) -> None:
        if self.structs:
            text = self._struct_refs(text)
        words = text.split(" ")
        first = words[0]
        second = words[1] if len(words) > 1 else ""
        rest = text[len(first) :].strip()

        if "@data" in names_in(text):
            raise AsmError(_DATA_SEGMENT_HINT)
        for word in (first, second):
            if word in _UNSUPPORTED_WORDS:
                raise AsmError(_UNSUPPORTED_WORDS[word])
            if word in UNSUPPORTED_DATA:
                raise AsmError(UNSUPPORTED_DATA[word])

        if self.nasm and self._nasm_directive(first, rest):
            return
        if first.startswith(".") and not self.nasm:
            self._dot_directive(number, first, rest)
            return
        if first in ("include", "%include"):
            if rest.strip("'\"<>") not in ("irvine32.inc", "macros.inc"):
                raise AsmError(
                    f"INCLUDE {rest} is not supported; Irvine32.inc and Macros.inc are built in"
                )
            return
        if first in ("align", "even") and not self.nasm:
            self._align(evaluate(rest, self.scope, 0) if rest else 2)
            return
        if second == "label" and len(words) > 2 and not self.nasm:
            self._label_directive(number, first, words[2])
            return
        if first in ("includelib", "option", "title", "page", "subttl"):
            return
        if second.rstrip(",") == "proto" or first == "public":
            return
        if first in ("extern", "extrn", "externdef"):
            raise AsmError(
                "EXTERN refers to a procedure in another source file; emu32 assembles one "
                "file at a time, so put that procedure in this file"
            )
        if first == "local":
            self._local(rest)
            return
        if first == "invoke":
            self._invoke(number, rest)
            return
        if first == "org":
            self.warnings.append(
                AsmMessage(number, "ORG is ignored; code starts at the code section")
            )
            return
        if first == "end":
            self.ended = True
            if rest:
                self.end_name = (rest, number)
            return
        constant = _CONSTANT_RE.match(text)
        if constant:
            self._constant(number, *constant.groups())
            return
        if self._data(number, words):
            return
        if not self.nasm and second.rstrip(",") == "proc":
            # Everything after PROC; MASM allows `name PROC, param:DWORD`.
            self._proc(number, first, rest[4:])
            return
        if not self.nasm and second == "endp":
            self._endp(first)
            return
        label = (_LOCAL_LABEL_RE if self.nasm else _LABEL_RE).match(text)
        if label and not text.startswith(("rep ", "lock ")):
            name, remainder = label.groups()
            self._code_label(number, name, scope_global=text.startswith(f"{name}::"))
            if remainder:
                self._instruction(number, remainder)
            return
        self._instruction(number, text)

    def _nasm_directive(self, first: str, rest: str) -> bool:
        if first in ("section", "segment"):
            name = rest.split(" ")[0]
            self.section = "code" if name in (".text", ".code") else "data"
            return True
        return first in ("global", "extern", "bits", "default", "cpu")

    def _dot_directive(self, number: int, word: str, rest: str) -> None:
        if word in (".data", ".data?", ".const"):
            self.section = "data"
        elif word == ".code":
            self.section = "code"
        elif word == ".stack" or _CPU_DIRECTIVE_RE.fullmatch(word):
            pass
        elif word == ".model":
            if not rest.startswith("flat"):
                self.warnings.append(
                    AsmMessage(
                        number, f".model {rest} is treated as flat: emu32 runs 32-bit programs"
                    )
                )
        elif word in _HIGH_LEVEL:
            raise AsmError(f"{word.upper()} is not supported; use CMP and conditional jumps")
        else:
            raise AsmError(f"unknown directive '{word}'")

    def _constant(self, number: int, name: str, expression: str) -> None:
        if not expression:
            raise AsmError(f"constant '{name}' has no value")
        if expression.startswith("<"):
            raise AsmError("text constants (EQU <...>) are not supported; use a number")
        value = evaluate(expression, self.scope, self.data.here)
        if name in self.scope.constants:
            self.scope.constants[name] = value  # `=` may redefine a constant
            return
        self._define(name, number)
        self.scope.constants[name] = value

    def _data(self, number: int, words: list[str]) -> bool:
        if len(words) > 1 and words[1] in self.structs:
            if self.section != "data":
                raise AsmError("data definitions belong in the .data section")
            self._define(words[0], number)
            self._struct_data(number, words[0], words[1], " ".join(words[2:]))
            return True

        def is_data(word: str) -> bool:
            return word in DATA_SIZES or word in RESERVE_SIZES or word == "times"

        if self.section == "data" and len(words) > 1 and is_data(words[1]):
            if words[0] in MNEMONICS:
                raise AsmError(f"'{words[0]}' is an instruction name and cannot name a variable")
        if is_data(words[0]):
            name, at = None, 0
        elif len(words) > 1 and is_data(words[1]) and words[0] not in MNEMONICS:
            name, at = words[0].rstrip(":"), 1
        else:
            return False
        if self.section != "data":
            raise AsmError("data definitions belong in the .data section")
        directive, operands = words[at], " ".join(words[at + 1 :])
        if directive == "times":
            count, directive, *values = operands.split(" ")
            operands = f"{count} dup({' '.join(values)})"
        if name:
            self._define(name, number)
        self.data.define(number, name, directive, operands)
        return True

    # STRUCT, LABEL and ALIGN

    def _layout(self, name: str) -> tuple[int, dict[str, tuple[int, int, int, bytes]]]:
        """Size of a STRUCT and each field's (offset, element size, count, default bytes)."""
        if name not in self.layouts:
            scratch = Scope(constants=self.scope.constants, externals=self.scope.externals)
            builder = DataBuilder(0, 1 << 20, scratch)
            fields = {}
            for item in self.structs[name]:
                if item.directive not in DATA_SIZES:
                    raise AsmError(
                        f"field '{item.name}' of {name}: use BYTE, WORD, DWORD or QWORD fields"
                    )
                start = len(builder.data)
                builder.define(0, item.name, item.directive, item.initializer)
                symbol = scratch.symbols[item.name]
                fields[item.name] = (start, symbol.size, symbol.count, bytes(builder.data[start:]))
            self.layouts[name] = (len(builder.data), fields)
        return self.layouts[name]

    def _struct_instance(self, name: str, text: str) -> bytes:
        text = text.strip()
        if not (text.startswith(("<", "{")) and text.endswith((">", "}"))):
            raise AsmError(f"a {name} value is written in angle brackets, for example <>")
        inner = text[1:-1].strip()
        values = split_args(inner) if inner else []
        _, fields = self._layout(name)
        if len(values) > len(fields):
            raise AsmError(f"{name} has {len(fields)} fields, but {len(values)} values are given")
        blob = bytearray()
        for index, (field_name, (_, _, _, default)) in enumerate(fields.items()):
            value = values[index] if index < len(values) else ""
            if not value:
                blob += default
                continue
            scratch = Scope(constants=self.scope.constants, externals=self.scope.externals)
            builder = DataBuilder(0, 1 << 20, scratch)
            field_def = next(f for f in self.structs[name] if f.name == field_name)
            builder.define(0, None, field_def.directive, value)
            if len(builder.data) > len(default):
                raise AsmError(f"the value for {name}.{field_name} is too long for the field")
            blob += builder.data + default[len(builder.data) :]
        return bytes(blob)

    def _struct_data(self, number: int, var: str, name: str, operands: str) -> None:
        size, _ = self._layout(name)
        blob, count = bytearray(), 0
        for item in split_args(operands) or ["<>"]:
            dup = re.fullmatch(r"(.+?)\s*dup\s*\((.*)\)", item)
            if dup:
                times = evaluate(dup.group(1), self.scope, self.data.here)
                blob += self._struct_instance(name, dup.group(2) or "<>") * times
                count += times
            else:
                blob += self._struct_instance(name, item)
                count += 1
        self.data.define_raw(number, var, bytes(blob), size, count, kind=name)
        self.struct_vars[var] = name

    def _field(self, name: str, field_name: str) -> tuple[int, int]:
        _, fields = self._layout(name)
        if field_name not in fields:
            raise AsmError(f"{name} has no field '{field_name}'")
        offset, size, _, _ = fields[field_name]
        return offset, size

    def _struct_refs(self, text: str) -> str:
        """`var.field`, `(Type PTR [reg]).field`, `Type.field`, `SIZEOF Type`, `TYPE Type`."""

        def sized(name: str, field_name: str, base: str) -> str:
            offset, size = self._field(name, field_name)
            return f"{SIZE_NAMES.get(size, 'byte')} ptr [{base}+{hex(offset)}]"

        def pointer(match: re.Match) -> str:
            name, inner, field_name = match.groups()
            if name not in self.structs:
                return match.group(0)
            return sized(name, field_name, inner.strip().strip("[]"))

        def dotted(match: re.Match) -> str:
            prefix, name, field_name = match.groups()
            if name in self.structs:
                return (prefix or "") + hex(self._field(name, field_name)[0])
            if name in self.struct_vars:
                offset, _ = self._field(self.struct_vars[name], field_name)
                if prefix:
                    return f"{prefix}{name}+{hex(offset)}"
                return sized(self.struct_vars[name], field_name, name)
            return match.group(0)

        def size_of(match: re.Match) -> str:
            if match.group(2) in self.structs:
                return hex(self._layout(match.group(2))[0])
            return match.group(0)

        def part(piece: str) -> str:
            piece = re.sub(rf"\b(sizeof|type)\s+({NAME})", size_of, piece)
            piece = re.sub(rf"\(({NAME})\s+ptr\s+([^()]*)\)\.({NAME})", pointer, piece)
            return re.sub(rf"(offset\s+)?(?<![\w@?$.])({NAME})\.({NAME})", dotted, piece)

        return map_unquoted(text, part)

    def _label_directive(self, number: int, name: str, type_name: str) -> None:
        """`name LABEL type`: another name and size for the data that follows."""
        if self.section == "code":
            self._code_label(number, name, scope_global=True)
            return
        if type_name in self.structs:
            size, kind = self._layout(type_name)[0], type_name
        elif type_name in _SIZE_OF_TYPE:
            size, kind = _SIZE_OF_TYPE[type_name], ""
        else:
            raise AsmError(f"unknown type '{type_name}' for LABEL")
        self._define(name, number)
        signed = type_name in ("sbyte", "sword", "sdword")
        self.scope.symbols[name] = Symbol(name, self.data.here, size, 1, signed, kind)

    def _align(self, boundary: int) -> None:
        if boundary <= 0 or boundary & (boundary - 1):
            raise AsmError(f"ALIGN needs a power of two, not {boundary}")
        if self.section == "data":
            pad = -self.data.here % boundary
            if pad:
                self.data.define_raw(0, None, bytes(pad), 1, pad)

    def _proc(self, number: int, name: str, options: str) -> None:
        """`name PROC [attributes] [USES regs] [,] [param:type, ...]`"""
        words = options.split()
        while words and words[0].rstrip(",") in _PROC_ATTRIBUTES:
            words.pop(0)
        text = " ".join(words)
        uses: list[str] = []
        if text.startswith("uses "):
            registers, _, text = text[5:].partition(",")
            uses = registers.split()
            for register in uses:
                if REGISTER_BITS.get(register) != self.mode.bits:
                    raise AsmError(f"USES needs 32-bit registers; '{register}' is not one")
        params: dict[str, tuple[int, int]] = {}
        for index, part in enumerate(split_operands(text.strip().lstrip(",").strip())):
            pname, colon, ptype = (piece.strip() for piece in part.partition(":"))
            if not colon:
                raise AsmError(f"parameter '{part}' needs a type, for example {part}:DWORD")
            params[pname] = (8 + 4 * index, self._type_size(ptype))
        self._code_label(number, name, scope_global=True)
        self.procs.append((name, number))
        self.local_labels.setdefault(name, set())
        self.frame = _Frame(name, number, uses, params) if uses or params else None

    @staticmethod
    def _type_size(type_text: str) -> int:
        if "ptr" in type_text.split():
            return 4  # pointers are addresses
        if type_text not in _SIZE_OF_TYPE:
            raise AsmError(f"unknown type '{type_text}'; use BYTE, WORD, DWORD or PTR")
        return _SIZE_OF_TYPE[type_text]

    def _local(self, text: str) -> None:
        """`LOCAL name:type, buffer[10]:BYTE` right after PROC: space below EBP."""
        if not self.procs:
            raise AsmError("LOCAL belongs inside a PROC")
        if self.frame is None:
            name, number = self.procs[-1]
            self.frame = _Frame(name, number, [], {})
        if self.frame.started:
            raise AsmError("LOCAL must come before the first instruction of the procedure")
        for part in split_operands(text):
            declared, colon, ltype = (piece.strip() for piece in part.partition(":"))
            size = self._type_size(ltype) if colon else 4
            match = re.fullmatch(rf"({NAME})\s*(?:\[(.+)\])?", declared)
            if match is None:
                raise AsmError(f"cannot read LOCAL '{part}'")
            count = evaluate(match.group(2), self.scope, 0) if match.group(2) else 1
            # Keep every local dword aligned, as stack slots are.
            self.frame.local_bytes += -(-(size * count) // 4) * 4
            self.frame.locals[match.group(1)] = (-self.frame.local_bytes, size)

    def _start_frame(self) -> None:
        """Emit the prologue before the procedure's first instruction or label."""
        frame = self.frame
        if frame is None or frame.started:
            return
        frame.started = True
        prologue = []
        if frame.uses_ebp:
            prologue += ["push ebp", "mov ebp, esp"]
            if frame.local_bytes:
                prologue.append(f"sub esp, {hex(frame.local_bytes)}")
        prologue += [f"push {register}" for register in frame.uses]
        for text in prologue:
            self.items.append(_Item(frame.line, text, proc=frame.name))

    def _endp(self, name: str) -> None:
        if not self.procs or self.procs[-1][0] != name:
            raise AsmError(f"ENDP for '{name}' does not match an open PROC")
        self.procs.pop()
        self.frame = None

    def _code_label(self, number: int, name: str, scope_global: bool = False) -> None:
        if self.section != "code":
            raise AsmError("code labels belong in the .code section")
        proc = self.procs[-1][0] if self.procs else None
        if proc and not scope_global:
            # MASM makes labels inside a PROC local to it, so procedures may reuse names.
            if name in KEYWORDS or name in MNEMONICS:
                raise AsmError(f"'{name}' is a reserved word and cannot be used as a name")
            if name in self.local_labels[proc]:
                raise AsmError(f"'{name}' is already defined in procedure '{proc}'")
            self.local_labels[proc].add(name)
            given, shown = f"__{proc}__{name}", f"{proc}.{name}"
            self._start_frame()
        else:
            self._define(name, number)
            given = shown = name
        self.items.append(_Item(number, given, label=True, proc=proc))
        self.labels.append(given)
        self.display[given] = shown

    def _instruction(self, number: int, text: str) -> None:
        if self.section != "code":
            raise AsmError("instructions belong in the .code section")
        proc = self.procs[-1][0] if self.procs else None
        frame = self.frame
        self._start_frame()
        mnemonic, _, operand = text.partition(" ")
        if frame is not None and mnemonic == "ret":
            # Undo the prologue, then return and remove the stack parameters (stdcall).
            epilogue = [f"pop {register}" for register in reversed(frame.uses)]
            if frame.uses_ebp:
                epilogue.append("leave")
            size = operand or (hex(4 * len(frame.params)) if frame.params else "")
            epilogue.append(f"ret {size}".strip())
            for line_text in epilogue:
                self.items.append(_Item(number, line_text, proc=proc, frame=frame))
            return
        self.items.append(_Item(number, text, proc=proc, frame=frame))

    def _invoke(self, number: int, text: str) -> None:
        if self.section != "code":
            raise AsmError("instructions belong in the .code section")
        self._start_frame()
        proc = self.procs[-1][0] if self.procs else None
        self.items.append(_Item(number, text, proc=proc, frame=self.frame, invoke=True))

    # Pass 2: rewrite operands and encode

    def _rewrite(self, text: str, item: _Item | None = None) -> str:
        if item is not None and item.proc and self.local_labels.get(item.proc):
            text = self._rename_local_labels(text, item.proc)
        mnemonic, _, operands = text.partition(" ")
        if not operands and mnemonic in self.scope.externals:
            # A routine name used as a statement, as in the course library's `exit`.
            return f"call {hex(self.scope.externals[mnemonic])}"
        # Keystone reads a bare `movsd` as the SSE2 instruction of the same name; the
        # explicit operands select the string instruction.
        if text.split(" ")[-1] == "movsd" and mnemonic in (*_PREFIXES, "movsd"):
            return text + " dword ptr es:[edi], dword ptr [esi]"
        if mnemonic in _PREFIXES or not operands:
            return text
        if (mnemonic.startswith(("j", "loop")) or mnemonic == "call") and re.search(
            r"(?<![\w@?$])\$\s*[+-]", operands
        ):
            raise AsmError("jumps to $+n or $-n are not supported; put a label at the target")
        operand_list = split_operands(operands)
        self._check_address_fits(mnemonic, operand_list)
        frame = item.frame if item is not None else None
        parts = []
        for op in operand_list:
            on_stack = self._frame_operand(op, frame) if frame else None
            parts.append(on_stack or rewrite_operand(op, self.scope, self.nasm))
        return f"{mnemonic} {', '.join(parts)}"

    def _rename_local_labels(self, text: str, proc: str) -> str:
        names = self.local_labels[proc]
        return map_unquoted(
            text,
            lambda part: re.sub(
                rf"(?<![\w@?$.])({NAME})",
                lambda m: f"__{proc}__{m.group(1)}" if m.group(1) in names else m.group(1),
                part,
            ),
        )

    def _frame_operand(self, op: str, frame: _Frame) -> str | None:
        """A parameter or LOCAL variable becomes memory relative to EBP, sized by its type."""
        variables = frame.variables
        used = [name for name in names_in(op) if name in variables]
        if not used:
            return None
        match = _FRAME_PTR_RE.match(op)
        size_word, body = (match.group(1).lstrip("s"), match.group(2)) if match else (None, op)
        pieces = [piece.strip() for piece in re.split(r"[\[\]]", body) if piece.strip()]
        expr = re.sub(
            rf"(?<![\w@?$.])({NAME})",
            lambda m: (
                _ebp_offset(variables[m.group(1)][0]) if m.group(1) in variables else m.group(1)
            ),
            "+".join(pieces),
        )
        expr = substitute_names(expr, self.scope.constants).replace("+-", "-").replace("++", "+")
        size_word = size_word or SIZE_NAMES[variables[used[0]][1]]
        return f"{size_word} ptr [{expr}]"

    def _expand_invoke(self, item: _Item) -> list[str]:
        """INVOKE pushes the arguments from last to first, then calls (stdcall: the
        procedure removes them). ADDR of a LOCAL variable goes through EAX, as in MASM."""
        target, *args = split_operands(item.text)
        variables = item.frame.variables if item.frame else {}
        out = []
        for arg in reversed(args):
            words = arg.split(" ", 1)
            if words[0] == "addr" and len(words) == 2:
                name = words[1].strip()
                if name in variables:
                    out += [f"lea eax, {name}", "push eax"]
                elif name in self.scope.symbols:
                    out.append(f"push offset {name}")
                else:
                    raise AsmError(f"ADDR needs a variable name, and '{name}' is not one")
            elif REGISTER_BITS.get(arg, self.mode.bits) < self.mode.bits:
                out += [f"movzx eax, {arg}", "push eax"]  # arguments are dwords
            else:
                out.append(f"push {arg}")
        out.append(f"call {target}")
        return out

    def _check_address_fits(self, mnemonic: str, operands: list[str]) -> None:
        """`lea dx, msg` and `mov dx, OFFSET msg` are the 16-bit habit; here addresses are
        32 bits, so DX would get a cut-off address and int 21h would print nothing."""
        if mnemonic not in ("mov", "lea") or len(operands) != 2:
            return
        dest, source = operands
        bits = REGISTER_BITS.get(dest)
        if bits is None or bits == self.mode.bits:
            return
        names = [n for n in names_in(source) if n in self.scope.symbols]
        if not names:
            return
        if mnemonic == "mov" and "offset" not in names_in(source):
            # MASM: `mov dx, msg` reads memory. NASM: it is the address unless in brackets.
            if not self.nasm or "[" in source:
                return
        wide = f"e{dest}" if f"e{dest}" in REGISTER_BITS else "edx"
        raise AsmError(
            f"{dest} is a {bits}-bit register and cannot hold the 32-bit address of "
            f"'{names[0]}'; use a 32-bit register: {mnemonic} {wide}, {source}"
        )

    def second_pass(self) -> Program | None:
        asm: list[str] = []
        instruction_lines: list[int] = []
        label_index: dict[str, int] = {}
        hidden: list[str] = []
        for item in self.items:
            if item.label:
                asm.append(f"{item.text}:")
                label_index[self.display[item.text]] = len(instruction_lines)
                continue
            try:
                texts = self._expand_invoke(item) if item.invoke else [item.text]
                texts = [self._rewrite(text, item) for text in texts]
                texts = [part for text in texts for part in _split_wait(text)]
            except AsmError as error:
                self.errors.append(AsmMessage(item.line, error.text))
                continue
            for text in texts:
                if _LOCATION_RE.search(map_unquoted(text, lambda p: p)):
                    # Keystone has no `$`; a hidden label before the instruction stands in.
                    here = f"__here_{len(hidden)}"
                    hidden.append(here)
                    asm.append(f"{here}:")
                    text = map_unquoted(text, lambda part, h=here: _LOCATION_RE.sub(h, part))
                asm.append(text)
                instruction_lines.append(item.line)

        ks = keystone.Ks(keystone.KS_ARCH_X86, self.mode.ks_mode)
        if self.nasm:
            ks.syntax = keystone.KS_OPT_SYNTAX_NASM
        base = self.mode.region("code").start
        code = b""
        if not self.errors:
            try:
                encoding, _ = ks.asm("\n".join(asm), base)
                code = bytes(encoding or b"")
            except keystone.KsError as error:
                self._find_line_errors(ks, asm, instruction_lines, [*self.labels, *hidden], error)
        else:
            self._find_line_errors(ks, asm, instruction_lines, [*self.labels, *hidden], None)
        if self.errors:
            return None

        if len(code) > self.mode.region("code").size:
            line = instruction_lines[-1] if instruction_lines else 0
            self.errors.append(AsmMessage(line, "the program code is larger than the code section"))
            return None

        cs = capstone.Cs(capstone.CS_ARCH_X86, self.mode.cs_mode)
        decoded = list(cs.disasm_lite(code, base))
        if len(decoded) != len(instruction_lines) or sum(d[1] for d in decoded) != len(code):
            raise AssemblyError(
                [AsmMessage(0, "internal error: the line map does not match the encoded code")]
            )
        addresses = [d[0] for d in decoded]
        end = base + len(code)
        labels = {
            name: addresses[i] if i < len(addresses) else end for name, i in label_index.items()
        }
        return Program(
            code=code,
            data=bytes(self.data.data),
            entry=self._entry(labels, base),
            symbols=dict(self.scope.symbols),
            constants=dict(self.scope.constants),
            labels=labels,
            address_to_line=dict(zip(addresses, instruction_lines, strict=True)),
            # A line may stand for several instructions (INVOKE, prologues); use the first.
            line_to_address=dict(reversed(list(zip(instruction_lines, addresses, strict=True)))),
            data_spans=dict(self.data.spans),
            warnings=self.warnings,
            mode=self.mode,
        )

    def _entry(self, labels: dict[str, int], base: int) -> int:
        if self.end_name:
            name, number = self.end_name
            if name not in labels:
                self.errors.append(
                    AsmMessage(number, f"END names '{name}', which is not a code label")
                )
                return base
            return labels[name]
        for name in ("main", "_start"):
            if name in labels:
                return labels[name]
        return labels[self.display[self.labels[0]]] if self.labels else base

    def _find_line_errors(self, ks, asm, instruction_lines, labels, whole_error) -> None:
        """Assemble each instruction alone, with every label defined after it, to find all
        bad lines; Keystone itself stops at the first error without naming its line."""
        tail = "\n".join(f"{name}:" for name in labels)
        base = self.mode.region("code").start
        failing = {e.line for e in self.errors}
        texts = [t for t in asm if not t.endswith(":")]
        found = False
        for number, text in zip(instruction_lines, texts, strict=True):
            if number in failing:
                continue
            try:
                ks.asm(f"{text}\n{tail}", base)
            except keystone.KsError as error:
                self.errors.append(AsmMessage(number, self._explain(error, text)))
                found = True
        if whole_error is not None and not found:
            line = instruction_lines[-1] if instruction_lines else 0
            self.errors.append(AsmMessage(line, f"assembly failed: {_ks_text(whole_error)}"))

    def _explain(self, error: keystone.KsError, text: str) -> str:
        mnemonic, _, operands = text.partition(" ")
        if error.errno == keystone.KS_ERR_ASM_MNEMONICFAIL:
            return f"unknown instruction '{mnemonic}'"
        if error.errno == keystone.KS_ERR_ASM_SYMBOL_MISSING:
            known = KEYWORDS | set(self.labels)
            unknown = [
                n for n in names_in(operands) if n not in known and not n.startswith("__here")
            ]
            return f"unknown name '{unknown[0]}'" if unknown else "unknown name"
        if error.errno == keystone.KS_ERR_ASM_INVALIDOPERAND:
            ptr = re.search(r"\b(byte|word|dword) ptr", operands)
            outside = [w for w in names_in(re.sub(r"\[.*?\]", "", operands)) if w in REGISTER_BITS]
            if ptr and outside and mnemonic not in _MIXED_SIZE:
                memory_bits = {"byte": 8, "word": 16, "dword": 32}[ptr.group(1)]
                if REGISTER_BITS[outside[0]] != memory_bits:
                    return (
                        f"operand sizes do not match: {outside[0]} is "
                        f"{REGISTER_BITS[outside[0]]} bits, the memory operand is "
                        f"{memory_bits} bits"
                    )
            return f"invalid operand in '{text}'"
        return _ks_text(error)


# These FPU instructions are a WAIT followed by the no-wait form, two instructions in the
# machine code; keeping them apart keeps one entry per instruction in the line map.
_WAIT_FORMS = {"finit", "fclex", "fstsw", "fstcw", "fsave", "fstenv"}


def _split_wait(text: str) -> list[str]:
    mnemonic, _, operands = text.partition(" ")
    if mnemonic not in _WAIT_FORMS:
        return [text]
    return ["wait", f"fn{mnemonic[1:]} {operands}".strip()]


def _ks_text(error: keystone.KsError) -> str:
    return re.sub(r"\s*\(KS_ERR_\w+\)", "", str(error)).lower()


def assemble(
    source: str,
    *,
    mode: CpuMode = MODE32,
    intel_syntax: bool = False,
    externals: dict[str, int] | None = None,
) -> Program:
    """Assemble source text. Raises AssemblyError listing every problem found."""
    lines, errors = clean(source)
    structs: dict[str, list[StructField]] = {}
    if not intel_syntax:
        lines, structs = preprocess(lines, errors)
    assembler = _Assembler(mode, intel_syntax, externals or {}, structs)
    assembler.errors.extend(errors)
    assembler.first_pass(lines)
    program = assembler.second_pass()
    if program is None or assembler.errors:
        raise AssemblyError(assembler.errors)
    return program
