"""Console I/O for programs: `int 21h` services and the library routines."""

from emu32.emulator import Emulator
from emu32.runtime import library_routines
from emu32.runtime.console import Console, InputCancelled
from emu32.runtime.services_int21 import handle_int21


def attach(emu: Emulator, console: Console) -> dict[str, int]:
    """Connect console services to an emulator, for this and every later load.

    Returns the library routine addresses to pass to the assembler as externals.
    """
    emu.interrupt_handlers[0x21] = lambda e: handle_int21(e, console)
    emu.setup_hooks.append(lambda e: library_routines.install(e, console))
    return library_routines.routine_addresses(emu.mode)


__all__ = ["Console", "InputCancelled", "attach"]
