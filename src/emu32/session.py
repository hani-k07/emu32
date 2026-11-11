"""Controller between the GUI and the engine.

Compiles and loads programs, steps and runs them, keeps breakpoints by source line, the
step-back history, watch expressions and a per-step trace record for the teaching views.
No Qt imports, so everything here is testable without a window.
"""

from __future__ import annotations

import bisect
import re
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, replace

import capstone
from capstone import x86_const as cs_x86

from emu32 import runtime
from emu32.assembler import Program, Symbol, assemble
from emu32.assembler.cleaner import clean_expression
from emu32.assembler.errors import AsmError
from emu32.assembler.operands import Scope, apply_operators, evaluate, substitute_names
from emu32.cpu_mode import MODE32, CpuMode
from emu32.emulator import Emulator, EmulatorError, MemoryAccess, RunResult, StopReason
from emu32.emulator.history import DEFAULT_LIMIT, History, HistoryEntry, undo
from emu32.runtime import Console

TRACE_LENGTH = 100
_ALU = {
    "add", "adc", "sub", "sbb", "cmp", "inc", "dec", "neg", "and", "or", "xor", "not", "test",
    "shl", "sal", "shr", "sar", "rol", "ror", "rcl", "rcr", "mul", "imul", "div", "idiv",
}  # fmt: skip
_NO_RESULT = {"cmp", "test"}
_IMPLICIT_ACCUMULATOR = {"mul", "imul", "div", "idiv"}
_BRACKET_RE = re.compile(r"\[([^\[\]]*)\]")


class SessionError(Exception):
    pass


@dataclass(frozen=True)
class AluOperation:
    operation: str  # mnemonic in capitals: ADD, SUB, CMP, SHL...
    inputs: tuple[int, ...]
    result: int | None  # None for CMP and TEST, which only set flags


@dataclass(frozen=True)
class TraceRecord:
    """Everything one single step did, for the trace and the CPU structure view."""

    address: int
    data: bytes
    text: str
    line: int | None
    before: dict[str, int]
    after: dict[str, int]
    accesses: tuple[MemoryAccess, ...]
    alu: AluOperation | None


@dataclass(frozen=True)
class Outcome:
    reason: StopReason
    steps: int
    message: str = ""
    line: int | None = None
    trace: TraceRecord | None = None
    approximate: bool = False  # steps is a lower bound (a long fast run)


class Session:
    def __init__(
        self,
        mode: CpuMode = MODE32,
        max_steps: int = 100_000_000,
        history_limit: int = DEFAULT_LIMIT,
    ) -> None:
        self.mode = mode
        self.emulator = Emulator(mode, max_steps)
        self.console = Console()
        self._externals = runtime.attach(self.emulator, self.console)
        self.program: Program | None = None
        self.source: str | None = None
        self.intel_syntax = False
        self.history = History(history_limit)
        self.trace: deque[TraceRecord] = deque(maxlen=TRACE_LENGTH)
        self.watches: list[str] = []
        self._breakpoint_lines: set[int] = set()
        self._addresses: list[int] = []
        self._cs = capstone.Cs(capstone.CS_ARCH_X86, mode.cs_mode)
        self._cs.detail = True
        self._stop_event = threading.Event()
        # Held while the engine runs. The window reads state only when it can take the lock;
        # otherwise it shows `live`, a snapshot published between chunks of a run.
        self.lock = threading.RLock()
        self.live: tuple[dict[str, int], int] = ({}, 0)
        self.emulator.on_chunk = self._publish
        self._listing: list[tuple[int, bytes, str, int | None]] = []

    @property
    def max_steps(self) -> int:
        return self.emulator.max_steps

    @max_steps.setter
    def max_steps(self, value: int) -> None:
        self.emulator.max_steps = value

    # Program

    def compile(self, source: str, intel_syntax: bool = False) -> Program:
        """Assemble without loading. Raises AssemblyError."""
        return assemble(
            source, mode=self.mode, intel_syntax=intel_syntax, externals=self._externals
        )

    def load(self, source: str, intel_syntax: bool = False) -> Program:
        program = self.compile(source, intel_syntax)
        self.source, self.intel_syntax = source, intel_syntax
        self._start(program)
        return program

    def reload(self, source: str | None = None) -> Program:
        """Assemble the source again (or new source) and load it. Breakpoints stay."""
        if source is None and self.source is None:
            raise SessionError("no program has been loaded")
        return self.load(self.source if source is None else source, self.intel_syntax)

    def reset(self) -> None:
        """Back to the initial state of the loaded program."""
        self._start(self._require())

    def _start(self, program: Program) -> None:
        self.program = program
        self._addresses = sorted(program.address_to_line)
        for address in self.emulator.breakpoints:
            self.emulator.remove_breakpoint(address)
        for line in self._breakpoint_lines:
            target = self._code_line_from(line)
            if target is not None:
                self.emulator.add_breakpoint(program.line_to_address[target])
        self.console.clear()
        self.history.clear()
        self.trace.clear()
        with self.lock:
            self.emulator.load(program.code, program.data, program.entry)
        self._listing = []
        self._publish()

    def _require(self) -> Program:
        if self.program is None:
            raise SessionError("no program is loaded")
        return self.program

    # Source lines

    def line_of(self, address: int | None) -> int | None:
        """Source line of the instruction at or containing `address`."""
        if self.program is None or address is None or not self._addresses:
            return None
        end = self.mode.region("code").start + len(self.program.code)
        if not self._addresses[0] <= address < end:
            return None
        index = bisect.bisect_right(self._addresses, address) - 1
        return self.program.address_to_line[self._addresses[index]]

    def current_line(self) -> int | None:
        return self.line_of(self.emulator.register(self.mode.instruction_pointer))

    def _code_line_from(self, line: int) -> int | None:
        """The first line at or after `line` that holds an instruction."""
        lines = sorted(self.program.line_to_address) if self.program else []
        index = bisect.bisect_left(lines, line)
        return lines[index] if index < len(lines) else None

    # Breakpoints

    @property
    def breakpoint_lines(self) -> frozenset[int]:
        return frozenset(self._breakpoint_lines)

    def toggle_breakpoint(self, line: int) -> int | None:
        """Toggle a breakpoint. With a program loaded, a line without an instruction moves to
        the next line that has one. Returns the line used, or None if no code follows."""
        target = line if self.program is None else self._code_line_from(line)
        if target is None:
            return None
        address = self.program.line_to_address[target] if self.program else None
        if target in self._breakpoint_lines:
            self._breakpoint_lines.discard(target)
            if address is not None:
                self.emulator.remove_breakpoint(address)
        else:
            self._breakpoint_lines.add(target)
            if address is not None:
                self.emulator.add_breakpoint(address)
        return target

    # Execution

    def step(self) -> Outcome:
        with self.lock:
            outcome = self._step()
        self._publish()
        return outcome

    def _step(self) -> Outcome:
        self._require()
        emu, ip = self.emulator, self.mode.instruction_pointer
        before = emu.registers()
        fpu_before = emu.fpu_state()
        insn = self._decode(before[ip])
        snapshot = (emu.total_steps, emu.exited, self.console.length())
        emu.start_recording()
        try:
            result = emu.step()
            # A call into a library routine runs the routine in the same step, so a single
            # step never stops inside a stub.
            while result.reason is StopReason.LIMIT and self._in_library(emu.register(ip)):
                more = emu.step()
                result = replace(more, steps=result.steps + more.steps)
        finally:
            accesses = tuple(emu.stop_recording())
        writes = tuple(a for a in accesses if a.kind == "write")
        if result.steps or writes:
            self.history.push(HistoryEntry(before, writes, *snapshot, fpu=fpu_before))
        record = None
        if insn is not None:
            after = emu.registers()
            record = TraceRecord(
                address=insn.address,
                data=bytes(insn.bytes),
                text=f"{insn.mnemonic} {insn.op_str}".strip(),
                line=self.line_of(insn.address),
                before=before,
                after=after,
                accesses=accesses,
                alu=self._alu(insn, before, after, accesses),
            )
            self.trace.append(record)
        return self._outcome(result, record)

    def step_over(self) -> Outcome:
        with self.lock:
            outcome = self._step_over()
        self._publish()
        return outcome

    def _step_over(self) -> Outcome:
        """Like step, but a CALL runs until it returns."""
        self._require()
        emu = self.emulator
        insn = self._decode(emu.register(self.mode.instruction_pointer))
        if insn is None or insn.mnemonic != "call" or self._calls_library(insn):
            return self.step()
        return_address = insn.address + insn.size
        stack = emu.register(self.mode.stack_pointer)
        temporary = return_address not in emu.breakpoints
        if temporary:
            emu.add_breakpoint(return_address)
        try:
            outcome = self.run()
            # A recursive call returns to the same address from deeper frames first.
            while (
                outcome.reason is StopReason.BREAKPOINT
                and emu.register(self.mode.instruction_pointer) == return_address
                and emu.register(self.mode.stack_pointer) < stack
            ):
                outcome = self.run()
        finally:
            if temporary:
                emu.remove_breakpoint(return_address)
        if (
            temporary
            and outcome.reason is StopReason.BREAKPOINT
            and emu.register(self.mode.instruction_pointer) == return_address
        ):
            return replace(outcome, reason=StopReason.LIMIT, message="")
        return outcome

    def run(self) -> Outcome:
        with self.lock:
            outcome = self._run()
        self._publish()
        return outcome

    def _run(self) -> Outcome:
        """Run until a breakpoint, the end, an error, Stop or the step limit. Clears the
        step-back history, which covers single steps only."""
        self._require()
        self.history.clear()
        return self._outcome(self.emulator.run())

    def run_with_delay(self, delay: float, on_step: Callable[[Outcome], None]) -> Outcome:
        """Step delay mode: one instruction per tick, `delay` seconds apart, calling on_step
        after each. Stops like Run: breakpoint, end, error, Stop or the step limit."""
        self._require()
        self._stop_event.clear()
        emu, ip = self.emulator, self.mode.instruction_pointer
        done = 0
        while True:
            outcome = self.step()
            done += outcome.steps
            on_step(outcome)
            line = self.current_line()
            if outcome.reason is not StopReason.LIMIT:
                return replace(outcome, steps=done)
            if done >= self.max_steps:
                return Outcome(
                    StopReason.LIMIT, done, f"step limit reached ({done:,} instructions)", line
                )
            if emu.register(ip) in emu.breakpoints:
                return Outcome(StopReason.BREAKPOINT, done, f"breakpoint at line {line}", line)
            if self._stop_event.is_set() or self._stop_event.wait(delay):
                return Outcome(StopReason.STOPPED, done, f"stopped at line {line}", line)

    def stop(self) -> None:
        """Stop a run from another thread, including one waiting for input."""
        self._stop_event.set()
        self.emulator.stop()
        self.console.cancel()

    def step_back(self) -> bool:
        entry = self.history.pop()
        if entry is None:
            return False
        undo(self.emulator, entry)
        self.console.truncate(entry.console_length)
        ip = self.mode.instruction_pointer
        if self.trace and self.trace[-1].address == entry.registers[ip]:
            self.trace.pop()
        return True

    def _outcome(self, result: RunResult, record: TraceRecord | None = None) -> Outcome:
        emu = self.emulator
        line = self.line_of(result.address) if result.address is not None else None
        here = line or self.current_line()
        reason = result.reason
        if reason is StopReason.ERROR:
            where = f"line {line}" if line else self.mode.format_address(result.address or 0)
            message = f"{where}: {result.message}"
        elif reason is StopReason.EXITED:
            message = result.message or "the program ended"
            if emu.exit_code:
                message += f" with exit code {emu.exit_code}"
        elif reason is StopReason.BREAKPOINT:
            message = f"breakpoint at line {here}"
        elif reason is StopReason.STOPPED:
            message = f"stopped at line {here}" if here else "stopped"
        else:
            message = result.message
        return Outcome(reason, result.steps, message, here, record, result.approximate)

    # State for the window. Call these only while holding `lock`, or when idle.

    def _publish(self) -> None:
        self.live = (self.emulator.registers(), self.emulator.total_steps)

    def set_register(self, name: str, value: int) -> None:
        """Change a register while paused (the window's register editor)."""
        with self.lock:
            self.emulator.set_register(name, value)
        self._publish()

    def read_bytes(self, start: int, length: int) -> list[int | None]:
        """Bytes in [start, start+length); None where no memory is mapped."""
        out: list[int | None] = [None] * length
        for region in self.mode.regions:
            low, high = max(start, region.start), min(start + length, region.end)
            if low < high:
                data = self.emulator.read_memory(low, high - low)
                out[low - start : high - start] = list(data)
        return out

    def listing(self) -> list[tuple[int, bytes, str, int | None]]:
        """The program's instructions: (address, bytes, text, source line)."""
        program = self._require()
        if not self._listing:
            base = self.mode.region("code").start
            # Jump and call targets show as label or routine names instead of addresses.
            names = {hex(address): label for label, address in program.labels.items()}
            names |= {
                hex(address): runtime.library_routines.DISPLAY_NAMES[name]
                for name, address in self._externals.items()
            }
            self._listing = [
                (insn.address, bytes(insn.bytes),
                 f"{insn.mnemonic} {names.get(insn.op_str, insn.op_str)}".strip(),
                 program.address_to_line.get(insn.address))
                for insn in self._cs.disasm(program.code, base)
            ]  # fmt: skip
        return self._listing

    def disassemble(self, address: int, count: int) -> list[tuple[int, bytes, str]]:
        """Decode up to `count` instructions from `address` (for code outside the program,
        such as a library stub)."""
        region = next((r for r in self.mode.regions if r.contains(address)), None)
        if region is None:
            return []
        data = self.emulator.read_memory(address, min(count * 15, region.end - address))
        return [
            (insn.address, bytes(insn.bytes), f"{insn.mnemonic} {insn.op_str}".strip())
            for insn in self._cs.disasm(data, address, count)
        ]

    # Decoding and trace details

    def _in_library(self, address: int) -> bool:
        return self.mode.region("library_stubs").contains(address)

    def _calls_library(self, insn: capstone.CsInsn) -> bool:
        op = insn.operands[0] if insn.operands else None
        return op is not None and op.type == cs_x86.X86_OP_IMM and self._in_library(op.imm)

    def _decode(self, address: int) -> capstone.CsInsn | None:
        region = next((r for r in self.mode.regions if r.contains(address)), None)
        if region is None:
            return None
        try:
            data = self.emulator.read_memory(address, min(16, region.end - address))
        except EmulatorError:
            return None
        return next(self._cs.disasm(data, address), None)

    def _alu(self, insn, before, after, accesses) -> AluOperation | None:
        mnemonic = insn.mnemonic
        if mnemonic not in _ALU:
            return None
        old = {**before, **self.mode.split_registers(before)}
        new = {**after, **self.mode.split_registers(after)}
        reads = [a.value for a in accesses if a.kind == "read"]
        writes = [a.value for a in accesses if a.kind == "write"]
        inputs = []
        for op in insn.operands:
            if op.type == cs_x86.X86_OP_REG:
                inputs.append(old.get(insn.reg_name(op.reg).upper(), 0))
            elif op.type == cs_x86.X86_OP_IMM:
                inputs.append(op.imm & ((1 << (8 * (op.size or 4))) - 1))
            elif op.type == cs_x86.X86_OP_MEM:
                inputs.append(reads[0] if reads else 0)
        accumulator = mnemonic in _IMPLICIT_ACCUMULATOR and len(insn.operands) == 1
        if accumulator:
            inputs.insert(0, before["EAX"])
        result = None
        if mnemonic not in _NO_RESULT and insn.operands:
            dest = insn.operands[0]
            if accumulator:
                result = after["EAX"]
            elif dest.type == cs_x86.X86_OP_REG:
                result = new.get(insn.reg_name(dest.reg).upper())
            elif dest.type == cs_x86.X86_OP_MEM and writes:
                result = writes[-1]
        return AluOperation(mnemonic.upper(), tuple(inputs), result)

    # Variables and watches

    def variable_value(self, symbol: Symbol) -> int:
        """Value of the first element, signed for SBYTE, SWORD and SDWORD."""
        value = int.from_bytes(self.emulator.read_memory(symbol.address, symbol.size), "little")
        if symbol.signed and value >> (8 * symbol.size - 1):
            value -= 1 << (8 * symbol.size)
        return value

    def variables(self) -> list[tuple[Symbol, int]]:
        program = self._require()
        return [(symbol, self.variable_value(symbol)) for symbol in program.symbols.values()]

    def evaluate(self, expression: str) -> int:
        """Evaluate a watch expression: registers, variables (their value), constants,
        numbers, + - * / mod, OFFSET/SIZEOF/LENGTHOF/TYPE, and [address] for a dword.
        Raises ValueError with a short message."""
        program = self._require()
        regs = self.emulator.registers()
        values = {name.lower(): v for name, v in regs.items()}
        values |= {n.lower(): v for n, v in self.mode.split_registers(regs).items()}
        values |= program.constants
        values |= {name: self.variable_value(s) for name, s in program.symbols.items()}
        try:
            text = apply_operators(clean_expression(expression), Scope(symbols=program.symbols))
            text = substitute_names(text, values)
            while match := _BRACKET_RE.search(text):
                address = evaluate(match.group(1), Scope(), 0)
                value = int.from_bytes(self.emulator.read_memory(address, 4), "little")
                text = text[: match.start()] + hex(value) + text[match.end() :]
            return evaluate(text, Scope(), regs[self.mode.instruction_pointer])
        except AsmError as error:
            raise ValueError(error.text) from None
        except EmulatorError as error:
            raise ValueError(str(error)) from None

    def watch_values(self) -> list[tuple[str, int | str]]:
        """Each watch with its value, or an error message."""
        values: list[tuple[str, int | str]] = []
        for expression in self.watches:
            try:
                values.append((expression, self.evaluate(expression)))
            except ValueError as error:
                values.append((expression, str(error)))
        return values


def syntax_words() -> dict[str, frozenset[str]]:
    """Word lists for syntax coloring, so the editor needs no assembler imports."""
    from emu32.assembler.data_pass import DATA_SIZES, RESERVE_SIZES
    from emu32.assembler.encode import MNEMONICS
    from emu32.assembler.operands import REGISTER_BITS

    directives = {
        *DATA_SIZES, *RESERVE_SIZES, "dup", "equ", "proc", "endp", "end", "include",
        "includelib", "offset", "ptr", "lengthof", "sizeof", "type", "times", "section",
        "global", "extern", "org", "option", "proto", "macro", "endm", "local", "struct",
        "struc", "ends", "textequ", "label", "align", "even", "invoke", "addr", "uses",
    }  # fmt: skip
    return {
        "instructions": MNEMONICS,
        "registers": frozenset(REGISTER_BITS),
        "directives": frozenset(directives),
        "routines": frozenset(runtime.library_routines.ROUTINES),
    }
