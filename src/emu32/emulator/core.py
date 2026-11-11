"""Unicorn wrapper: loads a program, single-steps it, and runs it in chunks."""

from __future__ import annotations

import enum
import gc
import sys
from collections.abc import Callable
from dataclasses import dataclass, replace

import capstone
import unicorn
from unicorn import x86_const

from emu32.cpu_mode import MODE32, CpuMode
from emu32.emulator import flags

HLT = 0xF4

if sys.version_info < (3, 12):
    # ponytail: unicorn 2.1.4's Python binding loses about two references to None for every
    # Uc it creates and frees (measured on Python 3.11). When None's count reaches zero,
    # Python aborts; CI on Linux hit that at exit after a few hundred program loads. From
    # 3.12 on, None is immortal. These references keep the count far from zero (about
    # 100,000 loads). Remove when the binding is fixed or 3.11 support ends. D56.
    _NONE_RESERVE = [None] * 200_000


WINDOWS_FPU_CONTROL = 0x027F
FPU_STATUS = x86_const.UC_X86_REG_FPSW
_FPU_REGISTERS = (
    *(x86_const.UC_X86_REG_FP0 + i for i in range(8)),
    x86_const.UC_X86_REG_FPSW,
    x86_const.UC_X86_REG_FPCW,
    x86_const.UC_X86_REG_FPTAG,
)


def extended_to_float(mantissa: int, exponent: int) -> float:
    """An 80-bit x87 value (64-bit mantissa, sign and 15-bit exponent) as a Python float."""
    sign = -1.0 if exponent & 0x8000 else 1.0
    exponent &= 0x7FFF
    if exponent == 0x7FFF:
        return sign * float("inf") if mantissa << 1 == 0 else float("nan")
    if exponent == 0 and mantissa == 0:
        return sign * 0.0
    try:
        return sign * mantissa * 2.0 ** (exponent - 16383 - 63)
    except OverflowError:
        return sign * float("inf")


class StopReason(enum.Enum):
    LIMIT = "limit"  # the requested number of steps ran; a single step ends this way
    EXITED = "exited"
    ERROR = "error"
    STOPPED = "stopped"
    BREAKPOINT = "breakpoint"


@dataclass(frozen=True)
class MemoryAccess:
    address: int
    kind: str  # "read" or "write"
    data: bytes  # bytes read, or bytes written
    old: bytes = b""  # for writes: the bytes that were there before

    @property
    def size(self) -> int:
        return len(self.data)

    @property
    def value(self) -> int:
        return int.from_bytes(self.data, "little")


@dataclass(frozen=True)
class RunResult:
    reason: StopReason
    steps: int
    message: str = ""
    address: int | None = None
    approximate: bool = False  # steps is a lower bound (D65)


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
    # About 10 ms of work per chunk while counting. The window thread gets the GIL back
    # between chunks; with 100,000 a run starved it for a whole second (D35).
    chunk_size = 10_000
    # A run counts every instruction exactly for this many steps (a Python call per block,
    # about 1 s per million). After that it drops the counting hook and runs at full speed
    # (about 0.03 s per million); a run that then ends inside a chunk knows its count only
    # to within that chunk. D65.
    exact_steps = 200_000
    fast_chunk_size = 200_000

    def __init__(self, mode: CpuMode = MODE32, max_steps: int = 100_000_000) -> None:
        self.mode = mode
        self.max_steps = max_steps
        # Handlers for `int n`. Interrupt numbers without a handler stop the program.
        self.interrupt_handlers: dict[int, Callable[[Emulator], None]] = {}
        # Called at the end of every load, with memory mapped, to add stubs and hooks.
        self.setup_hooks: list[Callable[[Emulator], None]] = []
        # Called in the running thread after each chunk of a run, while Unicorn is idle,
        # so a caller can take a snapshot for a live display.
        self.on_chunk: Callable[[], None] | None = None
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
        # Breakpoint address -> Unicorn hook handle. Each hook covers one address, so the
        # check runs in C and costs nothing at other addresses.
        self._breakpoints: dict[int, int | None] = {}
        self._skip_break: int | None = None
        self._break_hit: int | None = None
        self._recording: list[MemoryAccess] | None = None
        self._record_hooks: list[int] = []
        self._block_hook: int | None = None
        self._hlt_addresses: list[int] = []
        self._halt_at: int | None = None
        # True when total_steps is a lower bound (a fast run ended inside a chunk).
        self.steps_approximate = False

    # Loading

    def load(self, code: bytes, data: bytes = b"", entry: int | None = None) -> None:
        mode = self.mode
        code_region, data_region = mode.region("code"), mode.region("data")
        for name, blob, region in (("code", code, code_region), ("data", data, data_region)):
            if len(blob) > region.size:
                raise EmulatorError(
                    f"the program's {name} is {len(blob)} bytes; the limit is {region.size}"
                )
        self._recording = None
        self._block_starts.clear()
        # HLT ends the program. A one-address hook on each HLT notices it in fast runs too,
        # where no block hook is there to say how a chunk ended.
        self._hlt_addresses = [
            address
            for address, _size, mnemonic, _ops in self._cs.disasm_lite(code, code_region.start)
            if mnemonic == "hlt"
        ]
        self._new_engine()
        uc = self.uc
        uc.mem_write(code_region.start, code)
        uc.mem_write(data_region.start, data)

        # `ret` from the entry procedure lands on the exit stub, which ends the program.
        sp = mode.region("stack").end - mode.word_size
        uc.mem_write(sp, self._exit.to_bytes(mode.word_size, "little"))
        self.set_register(mode.stack_pointer, sp)
        self.set_register(mode.flags_register, mode.initial_flags)
        # A Windows process starts with the FPU at 53-bit precision, all exceptions masked.
        self.uc.reg_write(x86_const.UC_X86_REG_FPCW, WINDOWS_FPU_CONTROL)
        self.uc.reg_write(x86_const.UC_X86_REG_FPTAG, 0xFFFF)  # every register empty
        self.set_register(self._ip, code_region.start if entry is None else entry)
        self.total_steps = 0
        self.steps_approximate = False
        self.exited = False
        self.exit_code = 0
        self._cpu_fault = False

    def _new_engine(self) -> None:
        """A fresh Unicorn instance with the memory map, hooks, breakpoints and stubs."""
        uc = unicorn.Uc(unicorn.UC_ARCH_X86, self.mode.uc_mode)
        for region in self.mode.regions:
            uc.mem_map(region.start, region.size, region.perms)
        uc.mem_write(self._exit, bytes([HLT]))
        # A block hook costs far less than a per-instruction hook and still gives an exact
        # instruction count when a run ends partway through a chunk.
        self._block_hook = uc.hook_add(unicorn.UC_HOOK_BLOCK, self._on_block)
        for address in self._hlt_addresses:
            uc.hook_add(unicorn.UC_HOOK_CODE, self._on_hlt, begin=address, end=address)
        uc.hook_add(unicorn.UC_HOOK_INTR, self._on_interrupt)
        uc.hook_add(unicorn.UC_HOOK_MEM_INVALID, self._on_invalid_memory)
        self.uc = uc
        for address in self._breakpoints:
            self._breakpoints[address] = self._hook_breakpoint(address)
        self._record_hooks = []
        if self._recording is not None:
            self._record_hooks = self._add_record_hooks()
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

    # Breakpoints

    @property
    def breakpoints(self) -> frozenset[int]:
        return frozenset(self._breakpoints)

    def add_breakpoint(self, address: int) -> None:
        if address not in self._breakpoints:
            self._breakpoints[address] = self._hook_breakpoint(address) if self.uc else None

    def remove_breakpoint(self, address: int) -> None:
        handle = self._breakpoints.pop(address, None)
        if handle is not None and self.uc is not None:
            self.uc.hook_del(handle)

    def _hook_breakpoint(self, address: int) -> int:
        return self.uc.hook_add(
            unicorn.UC_HOOK_CODE, self._on_breakpoint, begin=address, end=address
        )

    def _on_breakpoint(self, uc: unicorn.Uc, address: int, size: int, _data: object) -> None:
        if address == self._skip_break:
            # A run that starts on a breakpoint executes that instruction.
            self._skip_break = None
            return
        self._break_hit = address
        uc.emu_stop()  # stops before the instruction runs

    # Memory access recording, used for single steps only

    def start_recording(self) -> None:
        self._recording = []
        self._record_hooks = self._add_record_hooks()

    def _add_record_hooks(self) -> list[int]:
        return [
            self.uc.hook_add(unicorn.UC_HOOK_MEM_READ, self._on_access),
            self.uc.hook_add(unicorn.UC_HOOK_MEM_WRITE, self._on_access),
        ]

    def stop_recording(self) -> list[MemoryAccess]:
        for handle in self._record_hooks:
            self.uc.hook_del(handle)
        self._record_hooks = []
        accesses, self._recording = self._recording or [], None
        return accesses

    def _on_access(
        self, uc: unicorn.Uc, access: int, address: int, size: int, value: int, _data: object
    ) -> None:
        try:
            current = bytes(uc.mem_read(address, size))
        except unicorn.UcError:
            return  # the invalid-memory hook reports this access
        if access == unicorn.UC_MEM_WRITE:
            data = (value & ((1 << (8 * size)) - 1)).to_bytes(size, "little")
            self._recording.append(MemoryAccess(address, "write", data, current))
        else:
            self._recording.append(MemoryAccess(address, "read", current))

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
        self._skip_break = self.register(self._ip)
        done = 0
        approximate = False
        try:
            while done < limit:
                counting = done < self.exact_steps
                if not counting and self._block_hook is not None:
                    self.uc.hook_del(self._block_hook)  # full speed from here on
                    self._block_hook = None
                size = self.chunk_size if counting else self.fast_chunk_size
                count = min(size, limit - done)
                executed = self._execute(count, counting)
                if executed is None:  # a fast chunk ended early: count unknown
                    executed, approximate = 0, True
                    self.steps_approximate = True
                done += executed
                self.total_steps += executed
                if self.on_chunk is not None:
                    self.on_chunk()
                pc = self.register(self._ip)
                if self._fault is not None:
                    message, address = self._fault
                    return RunResult(StopReason.ERROR, done, message, address, approximate)
                if self._exit_requested or pc == self._exit or self._halt_at == pc - 1:
                    self.exited = True
                    return RunResult(StopReason.EXITED, done, approximate=approximate)
                if self._break_hit is not None:
                    return RunResult(
                        StopReason.BREAKPOINT, done, address=self._break_hit,
                        approximate=approximate,
                    )  # fmt: skip
                if self._stop_requested:
                    return RunResult(StopReason.STOPPED, done, approximate=approximate)
            return RunResult(StopReason.LIMIT, done)
        finally:
            if self._block_hook is None and self.uc is not None:
                self._block_hook = self.uc.hook_add(unicorn.UC_HOOK_BLOCK, self._on_block)

    def _execute(self, count: int, counting: bool = True) -> int | None:
        """Run up to `count` instructions. Returns how many ran, or None when a chunk
        without the counting hook ended early."""
        self._counted = 0
        self._last_block = []
        self._fault = None
        self._break_hit = None
        self._exit_requested = False
        self._halt_at = None
        resume_at = None
        # No cyclic garbage collection while Unicorn runs: a collection started inside one
        # of our hooks could finalize, and close, another finished Unicorn instance in the
        # middle of this run.
        collecting = gc.isenabled()
        gc.disable()
        try:
            self.uc.emu_start(self.register(self._ip), self._exit, count=count)
        except unicorn.UcError as error:
            if self._fault is None:
                message = _UC_ERRORS.get(error.errno, str(error))
                self._fault = (message, self.register(self._ip))
        except HookStop as stop:
            self._stop_requested = True
            resume_at = stop.resume_at
        finally:
            if collecting:
                gc.enable()
        if self._cpu_fault:
            self._clear_cpu_fault()
        pc = self.register(self._ip)
        if not counting:
            ended_early = (
                self._fault or self._exit_requested or self._break_hit is not None
                or self._stop_requested or pc == self._exit or self._halt_at is not None
            )  # fmt: skip
            if resume_at is not None:
                self.set_register(self._ip, resume_at)
            return None if ended_early else count
        executed = self._counted
        # Blocks are counted when entered; drop the instructions of the last block that did
        # not complete (a fault, a stop request, or the count limit inside the block).
        if self._last_block and self._last_block[0] <= pc:
            executed -= sum(1 for start in self._last_block if start >= pc)
        if resume_at is not None:
            self.set_register(self._ip, resume_at)
            executed -= 1  # the interrupted instruction will run again
        return max(0, min(executed, count))

    def _clear_cpu_fault(self) -> None:
        """Stopping inside the interrupt hook leaves the CPU midway through raising the
        exception. Running again would then turn the next divide error into a double fault
        (interrupt 08h), and inside a session it could hang. A fresh Unicorn instance with the
        same memory and registers has no exception in progress; the program state stays the
        same. Faults are rare, so copying the memory (about 1.2 MB) costs nothing noticeable.
        """
        registers = self.registers()
        fpu = self.fpu_state()
        memory = [(r.start, bytes(self.uc.mem_read(r.start, r.size))) for r in self.mode.regions]
        self._new_engine()
        for start, blob in memory:
            self.uc.mem_write(start, blob)
        for name, value in registers.items():
            self.set_register(name, value)
        self.set_fpu_state(fpu)
        self._cpu_fault = False

    # Hooks

    def _on_hlt(self, uc: unicorn.Uc, address: int, size: int, _data: object) -> None:
        self._halt_at = address  # Unicorn stops right after the HLT itself

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
        if number < 32:
            self._cpu_fault = True  # a CPU exception, not an `int n` instruction
        if number == 0:
            # Divide error is a fault: EIP still points at the div or idiv.
            self._fault = ("divide error: division by zero, or the result is too large", pc)
        else:
            # Software interrupts are traps: EIP already points past the int instruction
            # (CD ib, or the one-byte INT3 / INTO / INT1).
            address = pc
            if self.read_memory(pc - 2, 1)[0] == 0xCD:
                address = pc - 2
            elif self.read_memory(pc - 1, 1)[0] in (0xCC, 0xCE, 0xF1):
                address = pc - 1
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

    def fpu_state(self) -> tuple:
        """The eight x87 data registers and the status, control and tag words."""
        return tuple(self.uc.reg_read(r) for r in _FPU_REGISTERS)

    def set_fpu_state(self, state: tuple) -> None:
        for register, value in zip(_FPU_REGISTERS, state, strict=True):
            self.uc.reg_write(register, value)

    def fpu_stack(self) -> list[float | None]:
        """ST(0) to ST(7) as numbers; None for an empty register."""
        status = self.uc.reg_read(x86_const.UC_X86_REG_FPSW)
        tags = self.uc.reg_read(x86_const.UC_X86_REG_FPTAG)
        top = (status >> 11) & 7
        out: list[float | None] = []
        for i in range(8):
            physical = (top + i) & 7
            if (tags >> (2 * physical)) & 3 == 3:  # tag 11: empty
                out.append(None)
                continue
            mantissa, exponent = self.uc.reg_read(x86_const.UC_X86_REG_FP0 + physical)
            out.append(extended_to_float(mantissa, exponent))
        return out

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
            if self._recording is not None:
                # Writes made by services (ReadString) are logged too, so step back undoes them.
                old = bytes(self.uc.mem_read(address, len(data)))
                self._recording.append(MemoryAccess(address, "write", bytes(data), old))
            self.uc.mem_write(address, data)
        except unicorn.UcError as error:
            raise EmulatorError(
                f"cannot write {len(data)} bytes at {self.mode.format_address(address)}"
            ) from error
