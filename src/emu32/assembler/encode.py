"""Assembler driver: sections and directives, code pass, line map, errors and listing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import capstone
import keystone

from emu32.assembler.cleaner import SourceLine, clean, map_unquoted
from emu32.assembler.data_pass import DATA_SIZES, RESERVE_SIZES, UNSUPPORTED_DATA, DataBuilder
from emu32.assembler.errors import AsmError, AsmMessage, AssemblyError
from emu32.assembler.operands import (
    KEYWORDS,
    NAME,
    REGISTER_BITS,
    Scope,
    Symbol,
    evaluate,
    names_in,
    rewrite_operand,
    split_operands,
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
    "invoke": "INVOKE is not supported; push the arguments and use CALL",
    "macro": "macros are not supported",
    "endm": "macros are not supported",
    "struct": "structures are not supported",
    "struc": "structures are not supported",
    "ends": "structures and segments are not supported",
    "segment": "segments are not supported; use .data and .code",
    "assume": "ASSUME is not needed: emu32 uses flat 32-bit memory without segments",
    "local": "LOCAL is not supported; keep variables in .data or on the stack",
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
class _Item:
    line: int
    text: str
    label: bool = False


class _Assembler:
    def __init__(self, mode: CpuMode, nasm: bool, externals: dict[str, int]) -> None:
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
            if rest.strip("'\"<>") not in ("irvine32.inc",):
                raise AsmError(f"INCLUDE {rest} is not supported; only Irvine32.inc is recognized")
            return
        if first in ("includelib", "option", "title", "page", "subttl"):
            return
        if second == "proto":
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
        if not self.nasm and second == "proc":
            self._proc(number, first, words[2:])
            return
        if not self.nasm and second == "endp":
            self._endp(first)
            return
        label = (_LOCAL_LABEL_RE if self.nasm else _LABEL_RE).match(text)
        if label and not text.startswith(("rep ", "lock ")):
            name, remainder = label.groups()
            self._code_label(number, name)
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

    def _proc(self, number: int, name: str, options: list[str]) -> None:
        extra = [w for w in options if w not in ("near", "public", "private")]
        if extra:
            raise AsmError(
                f"PROC options '{' '.join(extra)}' are not supported; "
                "save registers with PUSH and POP"
            )
        self._code_label(number, name)
        self.procs.append((name, number))

    def _endp(self, name: str) -> None:
        if not self.procs or self.procs[-1][0] != name:
            raise AsmError(f"ENDP for '{name}' does not match an open PROC")
        self.procs.pop()

    def _code_label(self, number: int, name: str) -> None:
        if self.section != "code":
            raise AsmError("code labels belong in the .code section")
        self._define(name, number)
        self.items.append(_Item(number, name, label=True))
        self.labels.append(name)

    def _instruction(self, number: int, text: str) -> None:
        if self.section != "code":
            raise AsmError("instructions belong in the .code section")
        self.items.append(_Item(number, text))

    # Pass 2: rewrite operands and encode

    def _rewrite(self, text: str) -> str:
        mnemonic, _, operands = text.partition(" ")
        if not operands and mnemonic in self.scope.externals:
            # A routine name used as a statement, as in the course library's `exit`.
            return f"call {hex(self.scope.externals[mnemonic])}"
        if mnemonic in _PREFIXES or not operands:
            return text
        if (mnemonic.startswith(("j", "loop")) or mnemonic == "call") and re.search(
            r"(?<![\w@?$])\$\s*[+-]", operands
        ):
            raise AsmError("jumps to $+n or $-n are not supported; put a label at the target")
        operand_list = split_operands(operands)
        self._check_address_fits(mnemonic, operand_list)
        parts = [rewrite_operand(op, self.scope, self.nasm) for op in operand_list]
        return f"{mnemonic} {', '.join(parts)}"

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
                label_index[item.text] = len(instruction_lines)
                continue
            try:
                text = self._rewrite(item.text)
            except AsmError as error:
                self.errors.append(AsmMessage(item.line, error.text))
                continue
            if _LOCATION_RE.search(map_unquoted(text, lambda p: p)):
                # Keystone has no `$`; a hidden label right before the instruction stands in.
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
            line_to_address={line: a for a, line in zip(addresses, instruction_lines, strict=True)},
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
        return labels[self.labels[0]] if self.labels else base

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
    assembler = _Assembler(mode, intel_syntax, externals or {})
    assembler.errors.extend(errors)
    assembler.first_pass(lines)
    program = assembler.second_pass()
    if program is None or assembler.errors:
        raise AssemblyError(assembler.errors)
    return program
