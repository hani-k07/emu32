import pytest

from emu32.emulator import StopReason
from emu32.gui.worker import SessionRunner
from emu32.session import Session


@pytest.fixture
def make_runner(qtbot):
    runners = []

    def make(_qtbot, source):
        session = Session()
        session.load(source)
        runners.append(SessionRunner(session))
        return runners[-1]

    yield make
    for runner in runners:
        runner.shutdown()


def test_run_in_worker_thread_and_stop(qtbot, make_runner):
    runner = make_runner(qtbot, ".code\nmain:\ninc eax\njmp main")
    runner.session.max_steps = 10**12
    with qtbot.waitSignal(runner.finished, timeout=5000) as finished:
        assert runner.start("run")
        assert not runner.start("step")  # busy
        qtbot.wait(100)
        runner.stop()
    assert finished.args[0].reason is StopReason.STOPPED
    assert not runner.busy


def test_output_arrives_as_signals(qtbot, make_runner):
    runner = make_runner(qtbot, ".code\nmain:\nmov eax, 42\ncall WriteDec\nexit")
    chunks = []
    runner.output.connect(chunks.append)
    with qtbot.waitSignal(runner.finished, timeout=5000) as finished:
        runner.start("run")
    assert finished.args[0].reason is StopReason.EXITED
    qtbot.waitUntil(lambda: chunks == ["42"], timeout=2000)


def test_step_delay_mode_reports_each_step(qtbot, make_runner):
    runner = make_runner(qtbot, ".code\nmain:\nnop\nnop\nnop\nret")
    steps = []
    runner.stepped.connect(steps.append)
    with qtbot.waitSignal(runner.finished, timeout=5000) as finished:
        runner.start("run", delay_ms=5)
    assert finished.args[0].reason is StopReason.EXITED
    qtbot.waitUntil(lambda: len(steps) == 4, timeout=2000)


def test_errors_come_back_as_values(qtbot, make_runner):
    runner = make_runner(qtbot, ".code\nmain:\nret")
    runner.session.program = None  # force a SessionError inside the worker
    with qtbot.waitSignal(runner.finished, timeout=5000) as finished:
        runner.start("step")
    assert isinstance(finished.args[0], Exception)
