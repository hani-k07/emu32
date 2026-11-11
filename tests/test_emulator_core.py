import threading

import pytest
from conftest import CODE, DATA, assemble

from emu32.cpu_mode import MODE32
from emu32.emulator import Emulator, EmulatorError, StopReason

EXIT = MODE32.region("exit_stub").start


def test_five_plus_three(run_asm):
    emu, result = run_asm("mov eax, 5\nadd eax, 3\nret")
    assert emu.register("EAX") == 8
    assert result.reason is StopReason.EXITED
    assert result.steps == 3


def test_initial_state():
    emu = Emulator()
    emu.load(assemble("nop"))
    sp = MODE32.region("stack").end - 4
    assert emu.register("ESP") == sp
    assert int.from_bytes(emu.read_memory(sp, 4), "little") == EXIT
    assert emu.register("EIP") == CODE
    assert emu.register("EFLAGS") == 0x202
    assert emu.flags()["IF"] == 1


def test_sub_registers():
    emu = Emulator()
    emu.load(assemble("nop"))
    emu.set_register("EAX", 0x12345678)
    emu.set_register("ESI", 0xAABBCCDD)
    split = MODE32.split_registers(emu.registers())
    assert (split["AX"], split["AH"], split["AL"], split["SI"]) == (0x5678, 0x56, 0x78, 0xCCDD)
    assert emu.register("AH") == 0x56
    emu.set_register("AL", 0x1FF)  # masked to the register width
    assert emu.register("EAX") == 0x123456FF


def test_single_step_moves_eip_and_counts():
    emu = Emulator()
    emu.load(assemble("mov eax, 1\nmov ebx, 2\nret"))
    assert emu.step().reason is StopReason.LIMIT
    assert emu.register("EIP") == CODE + 5
    assert emu.register("EAX") == 1 and emu.register("EBX") == 0
    emu.step()
    assert emu.step().reason is StopReason.EXITED
    assert emu.total_steps == 3
    assert emu.step().reason is StopReason.EXITED
    assert emu.total_steps == 3


@pytest.mark.parametrize("chunk_size", [*range(1, 26), 100_000])
def test_step_count_is_exact_for_any_chunk_size(run_asm, chunk_size):
    emu, result = run_asm("mov ecx, 10\ntop: add eax, ecx\nloop top\nret", chunk_size=chunk_size)
    assert result.reason is StopReason.EXITED
    assert emu.register("EAX") == 55
    assert result.steps == 1 + 10 * 2 + 1


def test_hlt_ends_the_program(run_asm):
    emu, result = run_asm("mov eax, 1\nhlt\nmov eax, 2")
    assert result.reason is StopReason.EXITED
    assert result.steps == 2
    assert emu.register("EAX") == 1


@pytest.mark.parametrize("chunk_size", [64, 100_000])
def test_step_limit_stops_an_infinite_loop(run_asm, chunk_size):
    emu, result = run_asm("top: inc eax\njmp top", max_steps=1_000_000, chunk_size=chunk_size)
    assert result.reason is StopReason.LIMIT
    assert result.steps == 1_000_000
    assert "step limit" in result.message
    assert emu.register("EAX") == 500_000


def test_stop_from_another_thread():
    emu = Emulator(max_steps=10**12)
    emu.load(assemble("top: inc eax\njmp top"))
    timer = threading.Timer(0.2, emu.stop)
    timer.start()
    result = emu.run()
    timer.join()
    assert result.reason is StopReason.STOPPED
    assert result.steps > 0
    # The program stays usable after a stop.
    assert emu.step().reason is StopReason.LIMIT


@pytest.mark.parametrize(
    ("source", "text", "address"),
    [
        ("mov eax, [0x10]", "reads memory at 00000010", CODE),
        ("nop\nmov dword ptr [0x400000], 1", "read-only", CODE + 1),
        ("mov eax, 0x500000\njmp eax", "does not hold code", DATA),
        ("jmp 0x100", "outside the program's memory", 0x100),
        ("ud2", "invalid instruction", CODE),
        ("xor ecx, ecx\ndiv ecx", "divide error", CODE + 2),
        ("nop\nint 0x21", "interrupt 21h is not supported", CODE + 1),
    ],
)
def test_runtime_errors_report_message_and_address(run_asm, source, text, address):
    emu, result = run_asm(source + "\nret")
    assert result.reason is StopReason.ERROR
    assert text in result.message
    assert result.address == address
    assert emu.registers()["EIP"] >= 0  # state stays readable


def test_error_step_count_excludes_the_faulting_instruction(run_asm):
    _, result = run_asm("mov eax, 1\nmov ebx, 2\nxor ecx, ecx\ndiv ecx\nret")
    assert result.steps == 3


def test_interrupt_handler_runs_and_execution_continues():
    emu = Emulator()
    emu.interrupt_handlers[0x21] = lambda e: e.set_register("EAX", 42)
    emu.load(assemble("int 0x21\nadd eax, 1\nret"))
    assert emu.run().reason is StopReason.EXITED
    assert emu.register("EAX") == 43


def test_load_rejects_oversized_code():
    with pytest.raises(EmulatorError, match="limit"):
        Emulator().load(b"\x90" * (MODE32.region("code").size + 1))


def test_run_without_program_is_an_error():
    with pytest.raises(EmulatorError):
        Emulator().run()
