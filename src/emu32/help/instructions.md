# Instruction reference

`dest` and `src` are registers, memory or constants. Two memory operands in one
instruction are not allowed, and both operands must have the same size unless
the instruction says otherwise.

Flags: CF carry, ZF zero, SF sign, OF overflow, PF parity, AF auxiliary carry,
DF direction. "Not changed" means the flag keeps its old value; "undefined"
means its value after the instruction must not be used.

## Moving data

| Instruction | Does | Flags |
|---|---|---|
| `mov dest, src` | dest = src | not changed |
| `movzx dest, src` | copy a smaller value and fill the upper bits with 0 | not changed |
| `movsx dest, src` | copy a smaller value and fill the upper bits with its sign bit | not changed |
| `lea dest, [address]` | dest = the address itself, no memory is read | not changed |
| `xchg a, b` | swap a and b | not changed |
| `push src` | ESP = ESP - 4, then store src at [ESP] | not changed |
| `pop dest` | load dest from [ESP], then ESP = ESP + 4 | not changed |
| `cdq` | fill EDX with the sign bit of EAX (before `idiv`) | not changed |
| `cwde` | sign-extend AX into EAX | not changed |

## Arithmetic

| Instruction | Does | Flags |
|---|---|---|
| `add dest, src` | dest = dest + src | CF, ZF, SF, OF, PF, AF |
| `adc dest, src` | dest = dest + src + CF | CF, ZF, SF, OF, PF, AF |
| `sub dest, src` | dest = dest - src | CF, ZF, SF, OF, PF, AF |
| `sbb dest, src` | dest = dest - src - CF | CF, ZF, SF, OF, PF, AF |
| `inc dest` | dest = dest + 1 | ZF, SF, OF, PF, AF; **CF not changed** |
| `dec dest` | dest = dest - 1 | ZF, SF, OF, PF, AF; **CF not changed** |
| `neg dest` | dest = 0 - dest | CF = 0 only if dest was 0; ZF, SF, OF, PF, AF |
| `cmp a, b` | computes a - b and keeps only the flags | CF, ZF, SF, OF, PF, AF |

CF is set when an unsigned result does not fit (a carry out, or a borrow in
subtraction). OF is set when a signed result does not fit: for example
`7FFFFFFFh + 1` sets OF but not CF, and `0FFFFFFFFh + 1` sets CF but not OF.

## Multiply and divide

| Instruction | Does | Flags |
|---|---|---|
| `mul src` | EDX:EAX = EAX * src, unsigned | CF = OF = 1 if EDX is not 0; others undefined |
| `imul src` | EDX:EAX = EAX * src, signed | CF = OF = 1 if the result needs EDX; others undefined |
| `imul dest, src` | dest = dest * src, signed, lower 32 bits kept | CF = OF = 1 if bits were lost |
| `div src` | EAX = EDX:EAX / src, EDX = remainder, unsigned | undefined |
| `idiv src` | the same, signed; use `cdq` first | undefined |

With 8-bit operands the registers are AX and AL/AH; with 16-bit, DX:AX.
Dividing by zero, or a quotient too large for EAX, stops the program with a
divide error. Clear EDX (or use `cdq`) before dividing.

## Logic

| Instruction | Does | Flags |
|---|---|---|
| `and dest, src` | bitwise AND | CF = OF = 0; ZF, SF, PF |
| `or dest, src` | bitwise OR | CF = OF = 0; ZF, SF, PF |
| `xor dest, src` | bitwise exclusive OR; `xor eax, eax` sets EAX to 0 | CF = OF = 0; ZF, SF, PF |
| `not dest` | flip every bit | not changed |
| `test a, b` | computes a AND b and keeps only the flags | CF = OF = 0; ZF, SF, PF |

## Shifts and rotates

| Instruction | Does |
|---|---|
| `shl dest, n` | shift left; 0 comes in on the right; same as `sal` |
| `shr dest, n` | shift right; 0 comes in on the left (unsigned divide by 2^n) |
| `sar dest, n` | shift right; the sign bit is copied in (signed divide by 2^n, rounding down) |
| `rol dest, n` | rotate left; bits leaving on the left come back on the right |
| `ror dest, n` | rotate right |

`n` is a constant or CL. Only the low 5 bits of the count are used, so a shift
by 32 shifts by 0. CF receives the last bit shifted out. A count of 0 changes no
flags. OF is defined only for a shift by 1.

## Jumps

| Instruction | Jumps if | Use after |
|---|---|---|
| `jmp label` | always | |
| `je` / `jz` | ZF = 1 (equal) | any compare |
| `jne` / `jnz` | ZF = 0 (not equal) | any compare |
| `ja` | above: CF = 0 and ZF = 0 | unsigned compare |
| `jae` / `jnc` | above or equal: CF = 0 | unsigned |
| `jb` / `jc` | below: CF = 1 | unsigned |
| `jbe` | below or equal: CF = 1 or ZF = 1 | unsigned |
| `jg` | greater: ZF = 0 and SF = OF | signed compare |
| `jge` | greater or equal: SF = OF | signed |
| `jl` | less: SF differs from OF | signed |
| `jle` | less or equal: ZF = 1 or SF differs from OF | signed |
| `js` / `jns` | SF = 1 / SF = 0 | |
| `jo` / `jno` | OF = 1 / OF = 0 | |
| `jecxz` | ECX = 0 | before a loop |

## Loops and procedures

| Instruction | Does |
|---|---|
| `loop label` | ECX = ECX - 1; jump if ECX is not 0. Flags not changed. With ECX = 0 at the start it runs 2^32 times. |
| `call label` | push the address of the next instruction, then jump |
| `ret` | pop an address and jump there |
| `ret n` | the same, then add n to ESP (removes arguments) |

## Strings

These use ESI (source) and EDI (destination) and move them by 1, 2 or 4 bytes
after each item: forward when DF = 0 (`cld`), backward when DF = 1 (`std`).

| Instruction | Does |
|---|---|
| `movsb`, `movsw`, `movsd` | copy from [ESI] to [EDI] |
| `stosb`, `stosw`, `stosd` | store AL, AX or EAX at [EDI] |
| `lodsb`, `lodsw`, `lodsd` | load [ESI] into AL, AX or EAX |
| `scasb` | compare AL with [EDI] |
| `cmpsb` | compare [ESI] with [EDI] |
| `rep` prefix | repeat ECX times |
| `repe` / `repz` | repeat while equal, at most ECX times |
| `repne` / `repnz` | repeat while not equal, at most ECX times |

## Others

| Instruction | Does |
|---|---|
| `nop` | nothing |
| `cld`, `std` | DF = 0, DF = 1 |
| `stc`, `clc`, `cmc` | set, clear or flip CF |
| `int 21h` | a console service; see the Syntax reference |
| `hlt` | ends the program in emu32 |

Any other 32-bit instruction that the assembler knows also works; the tables
list the ones courses use most.
