"""EFLAGS bits shown to the user, in display order."""

FLAG_BITS = {"CF": 0, "PF": 2, "AF": 4, "ZF": 6, "SF": 7, "DF": 10, "OF": 11, "IF": 9}


def decode(eflags: int) -> dict[str, int]:
    return {name: (eflags >> bit) & 1 for name, bit in FLAG_BITS.items()}
