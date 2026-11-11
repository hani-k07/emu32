"""Flag results checked against the Intel SDM, Vol. 2, for each instruction.

Only flags the manual defines for the instruction are checked; undefined flags are skipped.
"""

import pytest
from conftest import CODE

from emu32.emulator import StopReason

MIN = 0x8000_0000
MAX = 0x7FFF_FFFF
ALL = 0xFFFF_FFFF


def check(run_asm, source, expected_flags, expected_regs=None, **registers):
    emu, result = run_asm(source + "\nret", **registers)
    assert result.reason is StopReason.EXITED, result.message
    flags = emu.flags()
    assert {name: flags[name] for name in expected_flags} == expected_flags
    for name, value in (expected_regs or {}).items():
        assert emu.register(name) == value, name


@pytest.mark.parametrize(
    ("eax", "ebx", "result", "flags"),
    [
        (MAX, 1, MIN, {"CF": 0, "OF": 1, "SF": 1, "ZF": 0}),
        (ALL, 1, 0, {"CF": 1, "OF": 0, "SF": 0, "ZF": 1}),
        (MIN, MIN, 0, {"CF": 1, "OF": 1, "ZF": 1}),
        (0x0F, 1, 0x10, {"AF": 1, "PF": 0}),
        (1, 2, 3, {"AF": 0, "PF": 1, "CF": 0, "OF": 0}),
    ],
)
def test_add(run_asm, eax, ebx, result, flags):
    check(run_asm, "add eax, ebx", flags, {"EAX": result}, eax=eax, ebx=ebx)


@pytest.mark.parametrize(
    ("eax", "ebx", "result", "flags"),
    [
        (0, 1, ALL, {"CF": 1, "OF": 0, "SF": 1, "ZF": 0}),
        (MIN, 1, MAX, {"CF": 0, "OF": 1, "SF": 0}),
        (5, 5, 0, {"CF": 0, "OF": 0, "ZF": 1}),
        (0x10, 1, 0x0F, {"AF": 1}),
    ],
)
def test_sub(run_asm, eax, ebx, result, flags):
    check(run_asm, "sub eax, ebx", flags, {"EAX": result}, eax=eax, ebx=ebx)


@pytest.mark.parametrize(
    ("eax", "ebx", "flags"),
    [
        (3, 5, {"CF": 1, "ZF": 0, "SF": 1, "OF": 0}),
        (5, 5, {"CF": 0, "ZF": 1, "SF": 0, "OF": 0}),
        (ALL, 1, {"CF": 0, "ZF": 0, "SF": 1, "OF": 0}),  # -1 < 1 signed, above unsigned
        (MIN, 1, {"CF": 0, "OF": 1, "SF": 0}),
    ],
)
def test_cmp_sets_flags_and_keeps_operands(run_asm, eax, ebx, flags):
    check(run_asm, "cmp eax, ebx", flags, {"EAX": eax, "EBX": ebx}, eax=eax, ebx=ebx)


@pytest.mark.parametrize("carry", ["stc", "clc"])
def test_inc_and_dec_leave_carry_alone(run_asm, carry):
    cf = 1 if carry == "stc" else 0
    check(run_asm, f"{carry}\ninc eax", {"CF": cf, "ZF": 1}, {"EAX": 0}, eax=ALL)
    check(run_asm, f"{carry}\ndec eax", {"CF": cf, "SF": 1}, {"EAX": ALL}, eax=0)


def test_inc_and_dec_overflow(run_asm):
    check(run_asm, "inc eax", {"OF": 1, "SF": 1}, {"EAX": MIN}, eax=MAX)
    check(run_asm, "dec eax", {"OF": 1, "SF": 0}, {"EAX": MAX}, eax=MIN)


@pytest.mark.parametrize(
    ("eax", "result", "flags"),
    [
        (0, 0, {"CF": 0, "ZF": 1, "OF": 0}),
        (MIN, MIN, {"CF": 1, "OF": 1, "SF": 1}),
        (5, 0xFFFF_FFFB, {"CF": 1, "OF": 0, "SF": 1}),
    ],
)
def test_neg(run_asm, eax, result, flags):
    check(run_asm, "neg eax", flags, {"EAX": result}, eax=eax)


def test_shift_by_zero_changes_nothing(run_asm):
    # cmp sets ZF=1, stc sets CF=1; a zero count must leave both and the value alone.
    check(run_asm, "cmp eax, eax\nstc\nshl eax, cl", {"CF": 1, "ZF": 1}, {"EAX": 5}, eax=5, ecx=0)


def test_shift_count_is_masked_to_five_bits(run_asm):
    check(run_asm, "cmp eax, eax\nstc\nshl eax, cl", {"CF": 1, "ZF": 1}, {"EAX": 5}, eax=5, ecx=32)
    check(run_asm, "shl eax, cl", {}, {"EAX": 10}, eax=5, ecx=33)


@pytest.mark.parametrize(
    ("source", "eax", "result", "flags"),
    [
        ("shl eax, 1", MIN, 0, {"CF": 1, "OF": 1, "ZF": 1}),
        ("shl eax, 1", 0x4000_0000, MIN, {"CF": 0, "OF": 1, "SF": 1}),
        ("shl eax, 4", 0x1000_0001, 0x10, {"CF": 1}),
        ("shr eax, 1", 1, 0, {"CF": 1, "ZF": 1, "OF": 0}),
        ("shr eax, 1", MIN, 0x4000_0000, {"CF": 0, "OF": 1}),
        ("sar eax, 31", MIN, ALL, {"CF": 0, "SF": 1}),
        ("sar eax, 1", ALL, ALL, {"CF": 1, "OF": 0}),
        ("rol eax, 1", MIN, 1, {"CF": 1}),
        ("ror eax, 1", 1, MIN, {"CF": 1}),
    ],
)
def test_shifts_and_rotates(run_asm, source, eax, result, flags):
    check(run_asm, source, flags, {"EAX": result}, eax=eax)


@pytest.mark.parametrize(
    ("source", "eax", "ebx", "regs", "flags"),
    [
        ("mul ebx", 2, 3, {"EAX": 6, "EDX": 0}, {"CF": 0, "OF": 0}),
        ("mul ebx", 0x1_0000, 0x1_0000, {"EAX": 0, "EDX": 1}, {"CF": 1, "OF": 1}),
        ("imul ebx", ALL, ALL, {"EAX": 1, "EDX": 0}, {"CF": 0, "OF": 0}),
        ("imul ebx", 0xFFFF_FFFE, 3, {"EAX": 0xFFFF_FFFA, "EDX": ALL}, {"CF": 0, "OF": 0}),
        ("imul ebx", 0x1_0000, 0x1_0000, {"EAX": 0, "EDX": 1}, {"CF": 1, "OF": 1}),
        ("imul eax, ebx", 0x1_0000, 0x1_0000, {"EAX": 0}, {"CF": 1, "OF": 1}),
        ("imul eax, ebx", 7, 6, {"EAX": 42}, {"CF": 0, "OF": 0}),
    ],
)
def test_mul_and_imul(run_asm, source, eax, ebx, regs, flags):
    check(run_asm, source, flags, regs, eax=eax, ebx=ebx, edx=0x1234)


def test_div_and_idiv_results(run_asm):
    check(run_asm, "div ecx", {}, {"EAX": 3, "EDX": 1}, eax=7, edx=0, ecx=2)
    check(run_asm, "idiv ecx", {}, {"EAX": ALL, "EDX": ALL}, eax=0xFFFF_FFF9, edx=ALL, ecx=6)


@pytest.mark.parametrize(
    ("source", "registers"),
    [
        ("div ecx", {"eax": 7, "edx": 0, "ecx": 0}),
        ("div ecx", {"eax": 0, "edx": 1, "ecx": 1}),  # quotient does not fit in 32 bits
        ("idiv ecx", {"eax": MIN, "edx": ALL, "ecx": ALL}),  # -2^31 / -1
    ],
)
def test_divide_errors(run_asm, source, registers):
    _, result = run_asm(source + "\nret", **registers)
    assert result.reason is StopReason.ERROR
    assert "divide error" in result.message
    assert result.address == CODE


def test_logic_clears_carry_and_overflow(run_asm):
    check(run_asm, "stc\nand eax, ebx", {"CF": 0, "OF": 0, "ZF": 1}, {"EAX": 0}, eax=0xF0, ebx=0x0F)
    check(run_asm, "or eax, ebx", {"CF": 0, "SF": 1}, {"EAX": MIN | 1}, eax=MIN, ebx=1)
    check(run_asm, "xor eax, eax", {"ZF": 1, "PF": 1}, {"EAX": 0}, eax=1234)
    check(run_asm, "test eax, 1", {"ZF": 1}, {"EAX": 2}, eax=2)
    # not changes no flags.
    check(run_asm, "stc\nnot eax", {"CF": 1}, {"EAX": ALL}, eax=0)


def test_adc_and_sbb_use_carry(run_asm):
    check(run_asm, "stc\nadc eax, ebx", {"CF": 0}, {"EAX": 6}, eax=2, ebx=3)
    check(run_asm, "stc\nsbb eax, ebx", {"CF": 1}, {"EAX": ALL}, eax=3, ebx=3)


def test_direction_flag(run_asm):
    check(run_asm, "std", {"DF": 1})
    check(run_asm, "std\ncld", {"DF": 0})
