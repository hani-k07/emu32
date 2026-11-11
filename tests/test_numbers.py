import pytest

from emu32.numbers import NumberError, calculate, fits, parse, views


def test_views_of_a_negative_byte():
    v = views(-1, 8)
    assert (v.unsigned, v.signed, v.hexadecimal, v.octal, v.binary) == (
        255,
        -1,
        "FF",
        "377",
        "1111 1111",
    )


def test_views_of_32_bits():
    v = views(0x8000_0000, 32)
    assert (v.unsigned, v.signed, v.hexadecimal) == (2147483648, -2147483648, "80000000")
    assert views(300, 8).unsigned == 44  # wraps like the CPU would


@pytest.mark.parametrize(
    ("text", "base", "value"),
    [
        ("1010", 2, 10),
        ("0b1010", 2, 10),
        ("1010b", 2, 10),
        ("17", 8, 15),
        ("FF", 16, 255),
        ("0FFh", 16, 255),
        ("0xff", 16, 255),
        ("-5", 10, -5),
        ("1 000", 10, 1000),
    ],
)
def test_parse(text, base, value):
    assert parse(text, base) == value


def test_parse_rejects_wrong_digits():
    with pytest.raises(NumberError, match="base-2"):
        parse("102", 2)


def test_fits():
    assert fits(255, 8) and fits(-128, 8) and not fits(256, 8) and not fits(-129, 8)


@pytest.mark.parametrize(
    ("expression", "value"),
    [
        ("0FFh + 1", 256),
        ("0x10 * 2", 32),
        ("1010b or 0101b", 15),
        ("0F0h and 3Ch", 0x30),
        ("1 shl 4", 16),
        ("80h shr 3", 16),
        ("not 0", -1),
        ("~0 & 0xFF", 255),
        ("17 mod 5", 2),
        ("100 / 7", 14),
        ("(2 + 3) * 4", 20),
        ("377o", 255),
        ("0b1111 ^ 0b1010", 5),
        ("-5 + 2", -3),
    ],
)
def test_calculate(expression, value):
    assert calculate(expression) == value


@pytest.mark.parametrize("expression", ["", "1 +", "abc", "1 / 0", "1 shl 99", "2 ** 3"])
def test_calculate_errors(expression):
    with pytest.raises(NumberError):
        calculate(expression)
