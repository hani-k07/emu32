import os

import keystone
import pytest

from emu32.cpu_mode import MODE32
from emu32.emulator import Emulator

# Must be set before Qt creates the application, so GUI tests run headless.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

CODE = MODE32.region("code").start
DATA = MODE32.region("data").start

_ks = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32)


def assemble(source: str) -> bytes:
    """Plain Keystone assembly, so core tests do not depend on the emu32 front-end."""
    return bytes(_ks.asm(source, CODE)[0])


@pytest.fixture
def run_asm():
    """Load and run a snippet; keyword arguments preset registers, e.g. eax=5."""

    def run(source, *, data=b"", max_steps=None, chunk_size=None, **registers):
        emu = Emulator()
        if chunk_size:
            emu.chunk_size = chunk_size
        emu.load(assemble(source), data)
        for name, value in registers.items():
            emu.set_register(name.upper(), value)
        return emu, emu.run(max_steps)

    return run
