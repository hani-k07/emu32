"""Instruction families running through the emulator core: jumps, loops, stack, calls,
string instructions, conversions and moves."""

from conftest import DATA

from emu32.emulator import StopReason


def run_ok(run_asm, source, **kwargs):
    emu, result = run_asm(source + "\nret", **kwargs)
    assert result.reason is StopReason.EXITED, result.message
    return emu


def test_conditional_jumps_signed_and_unsigned(run_asm):
    source = """
        cmp eax, ebx
        jl  less
        mov ecx, 1
        jmp next
    less:
        mov ecx, 2
    next:
        cmp eax, ebx
        jb  below
        mov edx, 1
        ret
    below:
        mov edx, 2
    """
    emu = run_ok(run_asm, source, eax=0xFFFF_FFFF, ebx=1)
    assert (emu.register("ECX"), emu.register("EDX")) == (2, 1)


def test_loop_counts_down_ecx(run_asm):
    emu = run_ok(run_asm, "mov ecx, 5\ntop: inc eax\nloop top")
    assert (emu.register("EAX"), emu.register("ECX")) == (5, 0)


def test_push_pop_and_esp(run_asm):
    emu = run_ok(
        run_asm, "mov edx, esp\npush 5\npush 6\nmov esi, esp\npop eax\npop ebx\nmov edi, esp"
    )
    assert (emu.register("EAX"), emu.register("EBX")) == (6, 5)
    assert emu.register("EDX") - emu.register("ESI") == 8
    assert emu.register("EDI") == emu.register("EDX")


def test_call_and_ret(run_asm):
    emu = run_ok(run_asm, "call double\nadd eax, 1\nret\ndouble: add eax, eax", eax=4)
    assert emu.register("EAX") == 9


def test_rep_movsb_copies_bytes(run_asm):
    emu = run_ok(run_asm, "cld\nrep movsb", data=b"hello", esi=DATA, edi=DATA + 0x10, ecx=5)
    assert emu.read_memory(DATA + 0x10, 5) == b"hello"
    assert emu.register("ECX") == 0


def test_rep_stosd_fills_dwords(run_asm):
    emu = run_ok(run_asm, "cld\nrep stosd", eax=0x1122_3344, edi=DATA, ecx=3)
    assert emu.read_memory(DATA, 12) == bytes.fromhex("44332211") * 3
    assert emu.register("EDI") == DATA + 12


def test_repne_scasb_finds_a_byte(run_asm):
    emu = run_ok(run_asm, "cld\nrepne scasb", data=b"abcdef", eax=ord("d"), edi=DATA, ecx=6)
    assert emu.register("EDI") == DATA + 4  # one past the match
    assert emu.flags()["ZF"] == 1


def test_repe_cmpsb_and_lodsb(run_asm):
    emu = run_ok(
        run_asm,
        "cld\nrepe cmpsb\nmov esi, edi\nlodsb",
        data=b"abcXabcY",
        esi=DATA,
        edi=DATA + 4,
        ecx=4,
    )
    assert emu.flags()["ZF"] == 0  # stopped at X vs Y
    assert emu.register("AL") == 0  # byte after "abcY"


def test_std_makes_string_ops_go_down(run_asm):
    emu = run_ok(run_asm, "std\nstosb\ncld", eax=0x41, edi=DATA + 5)
    assert emu.read_memory(DATA + 5, 1) == b"A"
    assert emu.register("EDI") == DATA + 4


def test_sign_and_zero_extension(run_asm):
    emu = run_ok(
        run_asm,
        "movzx ecx, bl\nmovsx edx, bl\nmov eax, 0xFFFE\ncwde\nmov esi, eax\nmov eax, -5\ncdq",
        ebx=0x80,
    )
    assert emu.register("ECX") == 0x80
    assert emu.register("EDX") == 0xFFFF_FFFF  # from cdq of -5
    assert emu.register("ESI") == 0xFFFF_FFFE


def test_lea_and_xchg(run_asm):
    emu = run_ok(run_asm, "lea ecx, [eax + ebx*4 + 8]\nxchg eax, ebx", eax=1, ebx=2)
    assert emu.register("ECX") == 1 + 2 * 4 + 8
    assert (emu.register("EAX"), emu.register("EBX")) == (2, 1)


def test_memory_operands(run_asm):
    emu = run_ok(
        run_asm,
        f"mov eax, dword ptr [{DATA}]\nadd eax, dword ptr [{DATA + 4}]\n"
        f"mov dword ptr [{DATA + 8}], eax",
        data=(10).to_bytes(4, "little") + (32).to_bytes(4, "little"),
    )
    assert int.from_bytes(emu.read_memory(DATA + 8, 4), "little") == 42
