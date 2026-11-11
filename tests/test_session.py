import threading
import time

import pytest

from emu32.cpu_mode import MODE32
from emu32.emulator import StopReason
from emu32.session import Session, SessionError

DATA = MODE32.region("data").start
STACK = MODE32.region("stack")

LOOP = """INCLUDE Irvine32.inc
.data
total DWORD 0
.code
main PROC
    mov  ecx, 5
top:
    add  total, ecx
    loop top
    mov  eax, total
    call WriteDec
    exit
main ENDP
END main
"""
# Line numbers in LOOP
TOP_ADD, LOOP_LINE, MOV_EAX, CALL_WRITE = 8, 9, 10, 11


def loaded(source=LOOP, **kwargs):
    session = Session(**kwargs)
    session.load(source)
    return session


def run_in_thread(fn):
    box = {}
    thread = threading.Thread(target=lambda: box.setdefault("result", fn()))
    thread.start()
    return thread, box


# Load, reload, reset


def test_load_starts_at_entry_line():
    session = loaded()
    assert session.current_line() == 6
    assert session.program.instruction_count == 6


def test_commands_need_a_program():
    session = Session()
    with pytest.raises(SessionError):
        session.step()
    with pytest.raises(SessionError):
        session.reload()


def test_reset_restores_the_initial_state():
    session = loaded()
    assert session.run().reason is StopReason.EXITED
    assert session.console.output() == "15"
    session.reset()
    assert session.current_line() == 6
    assert session.console.output() == ""
    assert session.variables()[0][1] == 0
    assert session.run().reason is StopReason.EXITED


def test_reload_takes_new_source_and_keeps_breakpoints():
    session = loaded()
    session.toggle_breakpoint(MOV_EAX)
    session.reload(LOOP.replace("mov  ecx, 5", "mov  ecx, 2"))
    outcome = session.run()
    assert (outcome.reason, outcome.line) == (StopReason.BREAKPOINT, MOV_EAX)
    assert session.evaluate("total") == 3


# Breakpoints


def test_breakpoint_stops_each_time_through_a_loop():
    session = loaded()
    assert session.toggle_breakpoint(TOP_ADD) == TOP_ADD
    hits = []
    while (outcome := session.run()).reason is StopReason.BREAKPOINT:
        hits.append((outcome.line, session.emulator.register("ECX")))
        assert outcome.message == f"breakpoint at line {TOP_ADD}"
    assert hits == [(TOP_ADD, n) for n in (5, 4, 3, 2, 1)]
    assert outcome.reason is StopReason.EXITED


def test_removed_breakpoint_no_longer_stops():
    session = loaded()
    session.toggle_breakpoint(TOP_ADD)
    assert session.run().reason is StopReason.BREAKPOINT
    session.toggle_breakpoint(TOP_ADD)
    assert session.run().reason is StopReason.EXITED


def test_breakpoint_on_a_line_without_code_moves_to_the_next_instruction():
    session = loaded()
    assert session.toggle_breakpoint(7) == TOP_ADD  # `top:` holds no instruction
    assert session.toggle_breakpoint(14) is None  # nothing after END


def test_breakpoint_set_before_loading_applies_after_load():
    session = Session()
    session.toggle_breakpoint(MOV_EAX)
    session.load(LOOP)
    assert session.run().line == MOV_EAX


# Step, step over, step back


def test_step_into_library_call_does_not_stop_in_the_stub():
    session = loaded()
    session.toggle_breakpoint(CALL_WRITE)
    session.run()
    outcome = session.step()
    assert outcome.line == CALL_WRITE + 1
    assert session.console.output() == "15"


def test_step_over_runs_a_call_to_its_return():
    source = """.code
main PROC
    mov eax, 2
    call twice
    add eax, 1
    ret
main ENDP
twice PROC
    add eax, eax
    ret
twice ENDP
END main"""
    session = loaded(source)
    session.step()
    outcome = session.step_over()
    assert (outcome.reason, outcome.line) == (StopReason.LIMIT, 5)
    assert session.emulator.register("EAX") == 4
    session.reset()
    session.toggle_breakpoint(9)
    session.step()
    assert session.step_over().line == 9  # a breakpoint inside the call still stops


def test_step_over_a_recursive_call_waits_for_the_same_frame():
    source = """.code
main PROC
    mov ecx, 3
    call down
    ret
main ENDP
down PROC
    dec ecx
    jz  done
    call down
done:
    inc eax
    ret
down ENDP
END main"""
    session = loaded(source)
    session.toggle_breakpoint(10)  # the recursive call inside down
    session.run()
    session.toggle_breakpoint(10)  # remove it, or the deeper frame would stop there too
    outcome = session.step_over()
    assert outcome.line == 12
    assert session.emulator.register("EAX") == 2  # deeper frames finished, this one not yet


def test_step_back_after_100_steps_restores_every_state():
    source = """INCLUDE Irvine32.inc
.data
total DWORD 0
slots DWORD 8 dup(0)
.code
main PROC
again:
    mov  ecx, 8
fill:
    mov  esi, ecx
    dec  esi
    mov  slots[esi*4], ecx
    add  total, ecx
    push ecx
    pop  ebx
    mov  eax, total
    call WriteDec
    loop fill
    jmp  again
main ENDP
END main"""
    session = loaded(source)
    emu = session.emulator

    def state():
        return (
            emu.registers(),
            emu.read_memory(DATA, 36),
            emu.read_memory(STACK.end - 64, 64),
            session.console.output(),
        )

    states = [state()]
    for _ in range(100):
        assert session.step().reason is StopReason.LIMIT
        states.append(state())
    assert states[-1] != states[0]
    for expected in reversed(states[:-1]):
        assert session.step_back()
        assert state() == expected
    assert not session.step_back()


def test_step_back_after_the_program_ends():
    session = loaded(".code\nmain:\nmov eax, 1\nret")
    session.step()
    assert session.step().reason is StopReason.EXITED
    assert session.step_back()
    assert not session.emulator.exited
    assert session.current_line() == 4


def test_run_clears_history_and_history_has_a_limit():
    session = loaded(history_limit=5)
    for _ in range(8):
        session.step()
    assert len(session.history) == 5
    session.run()
    assert not session.step_back()


# Stop and limits


def test_stop_ends_an_infinite_loop():
    session = loaded(".code\nmain:\ninc eax\njmp main")
    session.max_steps = 10**12
    thread, box = run_in_thread(session.run)
    time.sleep(0.2)
    session.stop()
    thread.join(5)
    outcome = box["result"]
    assert outcome.reason is StopReason.STOPPED
    assert outcome.line in (3, 4)
    assert outcome.message.startswith("stopped at line")


def test_stop_while_waiting_for_input():
    session = loaded(".code\nmain:\ncall ReadInt\nexit")
    waiting = threading.Event()
    session.console.on_wait = lambda value: value and waiting.set()
    thread, box = run_in_thread(session.run)
    assert waiting.wait(5)
    session.stop()
    thread.join(5)
    assert box["result"].reason is StopReason.STOPPED


def test_step_limit():
    session = loaded(".code\nmain:\njmp main")
    session.max_steps = 1000
    outcome = session.run()
    assert (outcome.reason, outcome.steps) == (StopReason.LIMIT, 1000)
    assert "step limit" in outcome.message


def test_runtime_error_names_the_source_line():
    session = loaded(".code\nmain:\nxor ecx, ecx\ndiv ecx\nret")
    outcome = session.run()
    assert outcome.reason is StopReason.ERROR
    assert outcome.message.startswith("line 4: divide error")
    assert outcome.line == 4


def test_exit_code_in_message():
    session = loaded(".code\nmain:\npush 3\ncall ExitProcess")
    assert session.run().message == "the program ended with exit code 3"


# Step delay mode


def test_run_with_delay_steps_and_stops_at_breakpoints():
    session = loaded()
    session.toggle_breakpoint(MOV_EAX)
    seen = []
    outcome = session.run_with_delay(0.001, seen.append)
    assert (outcome.reason, outcome.line) == (StopReason.BREAKPOINT, MOV_EAX)
    assert len(seen) == outcome.steps == 11
    assert all(step.trace is not None for step in seen)


def test_run_with_delay_stops_during_the_pause():
    session = loaded(".code\nmain:\ninc eax\njmp main")
    thread, box = run_in_thread(lambda: session.run_with_delay(10, lambda _: None))
    time.sleep(0.1)
    session.stop()
    thread.join(5)
    assert box["result"].reason is StopReason.STOPPED


# Trace records, variables, watches


def test_trace_records_memory_access_and_alu():
    source = """.data
v DWORD 10
.code
main PROC
    mov  eax, v
    add  eax, 5
    cmp  eax, 15
    push eax
    mov  ebx, 3
    mul  ebx
    ret
main ENDP
END main"""
    session = loaded(source)
    records = [session.step().trace for _ in range(6)]
    load, add, cmp, push, _, mul = records
    assert (load.accesses[0].kind, load.accesses[0].address, load.accesses[0].value) == (
        "read",
        DATA,
        10,
    )
    assert load.alu is None and load.line == 5
    assert (add.alu.operation, add.alu.inputs, add.alu.result) == ("ADD", (10, 5), 15)
    assert (cmp.alu.operation, cmp.alu.result) == ("CMP", None)
    assert push.accesses[0].kind == "write" and push.accesses[0].value == 15
    assert (mul.alu.inputs, mul.alu.result) == ((15, 3), 45)
    assert mul.before["EAX"] == 15 and mul.after["EAX"] == 45
    assert list(session.trace) == records


def test_trace_keeps_the_last_100_steps():
    session = loaded(".code\nmain:\ninc eax\njmp main")
    for _ in range(150):
        session.step()
    assert len(session.trace) == 100


def test_variables_and_watches():
    source = """.data
neg_one SDWORD -1
count   BYTE 200
arr     DWORD 7, 8
limit = 4
.code
main:
    mov esi, OFFSET arr
    ret"""
    session = loaded(source)
    session.step()
    assert [(s.name, v) for s, v in session.variables()] == [
        ("neg_one", -1),
        ("count", 200),
        ("arr", 7),
    ]
    session.watches = ["esi", "[esi + 4]", "count + limit", "SIZEOF arr", "ax", "missing"]
    assert session.watch_values() == [
        ("esi", DATA + 5),
        ("[esi + 4]", 8),
        ("count + limit", 204),
        ("SIZEOF arr", 8),
        ("ax", 0),
        ("missing", "unknown name 'missing'"),
    ]


def test_run_again_after_a_divide_error_reports_it_again():
    session = loaded(".code\nmain:\nxor ecx, ecx\nmov eax, 10\ndiv ecx\nret")
    first = session.run()
    assert first.message.startswith("line 5: divide error")
    for again in (session.run(), session.step(), session.run()):
        assert again.reason is StopReason.ERROR
        assert again.message.startswith("line 5: divide error")
    session.set_register("ECX", 2)  # fix the divisor and go on
    assert session.run().reason is StopReason.EXITED
    assert session.emulator.register("EAX") == 5
