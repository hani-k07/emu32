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
    "struct": "structures are not supported",
    "struc": "structures are not supported",
    "ends": "structures and segments are not supported",
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


_SIZE_OF_TYPE = {"byte": 1, "sbyte": 1, "word": 2, "sword": 2, "dword": 4, "sdword": 4}
_PROC_ATTRIBUTES = {"near", "far", "public", "private", "stdcall", "c", "pascal"}
_FRAME_PTR_RE = re.compile(r"^(byte|sbyte|word|sword|dword|sdword)\s+ptr\s+(.*)$")


def _ebp_offset(offset: int) -> str:
    # Generated numbers are always hex: after Keystone has run in NASM mode, its default
    # number base stays 16 for the whole process, so a plain 12 would mean 18. D62.
    return f"ebp{'+' if offset >= 0 else '-'}{hex(abs(offset))}"


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
