"""Unicorn wrapper: loads a program, single-steps it, and runs it in chunks."""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass, replace

import capstone
import unicorn
from unicorn import x86_const

from emu32.cpu_mode import MODE32, CpuMode
from emu32.emulator import flags

HLT = 0xF4


class StopReason(enum.Enum):
    LIMIT = "limit"  # the requested number of steps ran; a single step ends this way
    EXITED = "exited"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass(frozen=True)
class RunResult:
    reason: StopReason
    steps: int
    message: str = ""
    address: int | None = None


class EmulatorError(Exception):
    pass


class HookStop(Exception):  # noqa: N818 - a control signal, not an error
    """Raised inside a hook to end the run as a normal Stop, for example when input is
    cancelled. The instruction being hooked does not run, so a later run retries it.
    `resume_at` moves EIP back, for hooks that fire after the instruction (interrupts)."""

    def __init__(self, resume_at: int | None = None) -> None:
        super().__init__()
        self.resume_at = resume_at


_INVALID_ACCESS = {
    unicorn.UC_MEM_READ_UNMAPPED: "reads memory at {addr}, which is outside the program's memory",
    unicorn.UC_MEM_WRITE_UNMAPPED: "writes memory at {addr}, which is outside the program's memory",
    unicorn.UC_MEM_FETCH_UNMAPPED: "jumps to {addr}, which is outside the program's memory",
    unicorn.UC_MEM_READ_PROT: "reads memory at {addr} in the {region} area, which is not readable",
    unicorn.UC_MEM_WRITE_PROT: "writes memory at {addr} in the {region} area, which is read-only",
    unicorn.UC_MEM_FETCH_PROT: "jumps to {addr} in the {region} area, which does not hold code",
}

_UC_ERRORS = {
    unicorn.UC_ERR_INSN_INVALID: "invalid instruction",
    unicorn.UC_ERR_EXCEPTION: "the CPU raised an exception",
}


class Emulator:
    chunk_size = 100_000

    def __init__(self, mode: CpuMode = MODE32, max_steps: int = 1_000_000) -> None:
        self.mode = mode
        self.max_steps = max_steps
        # Handlers for `int n`. Interrupt numbers without a handler stop the program.
        self.interrupt_handlers: dict[int, Callable[[Emulator], None]] = {}
        # Called at the end of every load, with memory mapped, to add stubs and hooks.
        self.setup_hooks: list[Callable[[Emulator], None]] = []
        self.uc: unicorn.Uc | None = None
        self.total_steps = 0
        self.exited = False
        self.exit_code = 0
        self._exit_requested = False
        self._ip = mode.instruction_pointer
        self._exit = mode.region("exit_stub").start
        self._reg_ids = {
            name: getattr(x86_const, f"UC_X86_REG_{name}")
            for name in (*mode.registers, *mode.sub_registers)
        }
        self._cs = capstone.Cs(capstone.CS_ARCH_X86, mode.cs_mode)
        self._block_starts: dict[tuple[int, int], list[int]] = {}
        self._counted = 0
        self._last_block: list[int] = []
        self._fault: tuple[str, int] | None = None
        self._stop_requested = False

    # Loading

    def load(self, code: bytes, data: bytes = b"", entry: int | None = None) -> None:
        mode = self.mode
        code_region, data_region = mode.region("code"), mode.region("data")
        for name, blob, region in (("code", code, code_region), ("data", data, data_region)):
            if len(blob) > region.size:
                raise EmulatorError(
                    f"the program's {name} is {len(blob)} bytes; the limit is {region.size}"
                )
        uc = unicorn.Uc(unicorn.UC_ARCH_X86, mode.uc_mode)
        for region in mode.regions:
            uc.mem_map(region.start, region.size, region.perms)
        uc.mem_write(self._exit, bytes([HLT]))
        uc.mem_write(code_region.start, code)
        uc.mem_write(data_region.start, data)
        # A block hook costs far less than a per-instruction hook and still gives an exact
        # instruction count when a run ends partway through a chunk.
        uc.hook_add(unicorn.UC_HOOK_BLOCK, self._on_block)
        uc.hook_add(unicorn.UC_HOOK_INTR, self._on_interrupt)
        uc.hook_add(unicorn.UC_HOOK_MEM_INVALID, self._on_invalid_memory)
        self.uc = uc
        self._block_starts.clear()

        # `ret` from the entry procedure lands on the exit stub, which ends the program.
        sp = mode.region("stack").end - mode.word_size
        uc.mem_write(sp, self._exit.to_bytes(mode.word_size, "little"))
        self.set_register(mode.stack_pointer, sp)
        self.set_register(mode.flags_register, mode.initial_flags)
        self.set_register(self._ip, code_region.start if entry is None else entry)
        self.total_steps = 0
        self.exited = False
        self.exit_code = 0
        for setup in self.setup_hooks:
            setup(self)

    # Execution

    def step(self) -> RunResult:
        return self._advance(1)

    def run(self, max_steps: int | None = None) -> RunResult:
        limit = self.max_steps if max_steps is None else max_steps
        result = self._advance(limit)
        if result.reason is StopReason.LIMIT:
            return replace(result, message=f"step limit reached ({limit:,} instructions)")
        return result

    def stop(self) -> None:
        """Ask a running `run` to stop. Safe to call from another thread."""
        self._stop_requested = True
        if self.uc is not None:
            self.uc.emu_stop()

    def exit_program(self, code: int = 0) -> None:
        """End the program from inside a hook (exit services)."""
        self.exit_code = code
        self._exit_requested = True
        self.uc.emu_stop()

    def fail(self, message: str, address: int) -> None:
        """Stop the program with an error from inside a hook."""
        self._fault = (message, address)
        self.uc.emu_stop()

    def _advance(self, limit: int) -> RunResult:
        if self.uc is None:
            raise EmulatorError("no program is loaded")
        if self.exited:
            return RunResult(StopReason.EXITED, 0, "the program has ended")
        self._stop_requested = False
        done = 0
        while done < limit:
            count = min(self.chunk_size, limit - done)
            executed = self._execute(count)
            done += executed
            self.total_steps += executed
            pc = self.register(self._ip)
            if self._fault is not None:
                message, address = self._fault
                return RunResult(StopReason.ERROR, done, message, address)
            if (
                self._exit_requested
                or pc == self._exit
                or (executed < count and self._halted_before(pc))
            ):
                self.exited = True
                return RunResult(StopReason.EXITED, done)
            if self._stop_requested:
                return RunResult(StopReason.STOPPED, done)
        return RunResult(StopReason.LIMIT, done)

    def _execute(self, count: int) -> int:
        self._counted = 0
        self._last_block = []
        self._fault = None
        self._exit_requested = False
        resume_at = None
        try:
            self.uc.emu_start(self.register(self._ip), self._exit, count=count)
        except unicorn.UcError as error:
            if self._fault is None:
                message = _UC_ERRORS.get(error.errno, str(error))
                self._fault = (message, self.register(self._ip))
        except HookStop as stop:
            self._stop_requested = True
            resume_at = stop.resume_at
        pc = self.register(self._ip)
        executed = self._counted
        # Blocks are counted when entered; drop the instructions of the last block that did
        # not complete (a fault, a stop request, or the count limit inside the block).
        if self._last_block and self._last_block[0] <= pc:
            executed -= sum(1 for start in self._last_block if start >= pc)
        if resume_at is not None:
            self.set_register(self._ip, resume_at)
            executed -= 1  # the interrupted instruction will run again
        return max(0, min(executed, count))

    def _halted_before(self, pc: int) -> bool:
        return pc - 1 in self._last_block and self.read_memory(pc - 1, 1)[0] == HLT

    # Hooks

    def _on_block(self, uc: unicorn.Uc, address: int, size: int, _data: object) -> None:
        key = (address, size)
        starts = self._block_starts.get(key)
        if starts is None:
            # ponytail: cache assumes code never changes; holds because code regions are
            # read-only. Clear the cache on writes if self-modifying code is ever allowed.
            code = bytes(uc.mem_read(address, size))
            starts = [insn[0] for insn in self._cs.disasm_lite(code, address)]
            self._block_starts[key] = starts
        self._counted += len(starts)
        self._last_block = starts

    def _on_interrupt(self, uc: unicorn.Uc, number: int, _data: object) -> None:
        handler = self.interrupt_handlers.get(number)
        if handler is not None:
            handler(self)
            return
        pc = self.register(self._ip)
        if number == 0:
            # Divide error is a fault: EIP still points at the div or idiv.
            self._fault = ("divide error: division by zero, or the result is too large", pc)
        else:
            # Software interrupts are traps: EIP already points past the int instruction.
            earlier = [start for start in self._last_block if start < pc]
            address = earlier[-1] if earlier else pc
            self._fault = (f"interrupt {number:02X}h is not supported", address)
        uc.emu_stop()

    def _on_invalid_memory(
        self, uc: unicorn.Uc, access: int, address: int, size: int, value: int, _data: object
    ) -> bool:
        region = next((r.name for r in self.mode.regions if r.contains(address)), "unknown")
        template = _INVALID_ACCESS.get(access, "accesses memory at {addr}")
        message = "the program " + template.format(
            addr=self.mode.format_address(address), region=region.replace("_", " ")
        )
        # A bad fetch has no faulting instruction of its own; report the target address.
        fetch = access in (unicorn.UC_MEM_FETCH_UNMAPPED, unicorn.UC_MEM_FETCH_PROT)
        self._fault = (message, address if fetch else self.register(self._ip))
        return False

    # State access

    def register(self, name: str) -> int:
        return self.uc.reg_read(self._reg_ids[name])

    def set_register(self, name: str, value: int) -> None:
        width = self.mode.sub_registers[name][2] if name in self.mode.sub_registers else None
        self.uc.reg_write(self._reg_ids[name], value & ((1 << (width or self.mode.bits)) - 1))

    def registers(self) -> dict[str, int]:
        return {name: self.register(name) for name in self.mode.registers}

    def flags(self) -> dict[str, int]:
        return flags.decode(self.register(self.mode.flags_register))

    def read_memory(self, address: int, size: int) -> bytes:
        try:
            return bytes(self.uc.mem_read(address, size))
        except unicorn.UcError as error:
            raise EmulatorError(
                f"cannot read {size} bytes at {self.mode.format_address(address)}"
            ) from error

    def write_memory(self, address: int, data: bytes) -> None:
        try:
            self.uc.mem_write(address, data)
        except unicorn.UcError as error:
            raise EmulatorError(
                f"cannot write {len(data)} bytes at {self.mode.format_address(address)}"
            ) from error
