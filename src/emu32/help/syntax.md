# Syntax reference

emu32 accepts the MASM style used in most computer organization courses, and an
Intel/NASM style (see the end of this page). Upper and lower case mean the same
thing everywhere except inside strings.

## Program layout

```
INCLUDE Irvine32.inc        ; optional; the library routines are built in
.data
message BYTE "Hi", 0        ; variables
.code
main PROC                   ; the program starts here
    ...
    exit                    ; end the program
main ENDP
END main
```

| Line | Meaning |
|---|---|
| `.data` | variables follow |
| `.code` | instructions follow |
| `.stack 4096` | accepted; the stack is always 1 MB |
| `.386`, `.486`, `.586`, `.686` | accepted and ignored |
| `.model flat` | accepted; `.model small` is accepted with a warning |
| `INCLUDE Irvine32.inc` | accepted and ignored; the routines are built in |
| `name PROC` ... `name ENDP` | a procedure; its name is a label |
| `END main` | the program starts at `main` |

The program starts at the label named by `END`; without one, at `main`, then at
the first label in `.code`.

## Comments

Everything after `;` on a line is a comment (except a `;` inside a string).

## Numbers

| Written | Value |
|---|---|
| `10` or `10d` | ten, decimal |
| `0Ah` | hex; must start with a digit, so write `0FFh`, not `FFh` |
| `0x0A` | hex |
| `1010b` | binary |
| `'A'` | the character code, 65 |

## Variables

```
count   DWORD 0                 ; one 32-bit value
small   BYTE  -1                ; one byte
table   WORD  1, 2, 3           ; three 16-bit values
text    BYTE  "Hello", 13, 10, 0
buffer  BYTE  80 DUP(0)         ; 80 bytes of 0
grid    DWORD 3 DUP(4 DUP(?))   ; 12 values, not initialized
temp    SDWORD -40              ; signed: the Vars window shows it as negative
```

| Directive | Size | Same as |
|---|---|---|
| `BYTE`, `SBYTE` | 1 byte | `db` |
| `WORD`, `SWORD` | 2 bytes | `dw` |
| `DWORD`, `SDWORD` | 4 bytes | `dd` |

`?` means "no particular value" (emu32 stores 0). Strings may use single or
double quotes.

## Constants

```
LIMIT  EQU 100
step   = 4          ; = may be given a new value later
length = $ - text   ; $ is the current address in .data
```

## Using variables in instructions

A variable name means the memory at its address, and the size comes from the
variable:

| You write | Meaning |
|---|---|
| `mov eax, count` | read the DWORD at `count` |
| `mov count, eax` | write it |
| `inc small` | add 1 to one byte |
| `mov ax, table[4]` or `[table + 4]` | the WORD 4 bytes after the start (the third element) |
| `mov eax, arr[esi*4]` | element number ESI of a DWORD array |
| `mov esi, OFFSET text` | the address itself |
| `mov ecx, LENGTHOF table` | number of elements (3) |
| `mov ecx, SIZEOF table` | number of bytes (6) |
| `mov ecx, TYPE table` | bytes per element (2) |
| `mov al, BYTE PTR count` | read one byte of a DWORD |

Writing `mov al, count` when `count` is a DWORD is an error: the sizes do not
match.

## Library routines

Call them with `call Name`. They keep all registers except the ones they return
values in.

| Routine | Does |
|---|---|
| `WriteString` | prints the text at EDX, up to a 0 byte |
| `WriteChar` | prints the character in AL |
| `WriteInt` | prints EAX as a signed number with its sign: `+5`, `-5` |
| `WriteDec` | prints EAX as an unsigned number |
| `WriteHex` | prints EAX as eight hex digits |
| `Crlf` | starts a new line |
| `ReadInt` | reads a line into EAX; OF=1 and EAX=0 if it is not a number |
| `ReadChar` | reads one character into AL, without showing it; Enter gives 0Dh |
| `ReadString` | reads a line into the buffer at EDX; ECX is the buffer size; EAX returns the length |
| `DumpRegs` | prints all registers and flags |
| `exit` | ends the program; can be written alone as `exit` |
| `ExitProcess` | ends the program; `push 0` then `call ExitProcess` |

## int 21h services

Put the function number in AH, then write `int 21h`.

| AH | Does |
|---|---|
| `01h` | reads one character into AL and shows it |
| `02h` | prints the character in DL |
| `09h` | prints the text at EDX, up to a `$` |
| `4Ch` | ends the program; AL is the exit code |
| `40h` | prints EDX as a signed decimal number (emu32 only; in DOS this function writes to a file) |

## Memory

| Area | Address | Notes |
|---|---|---|
| code | `00400000` | read-only: writing here is an error |
| data | `00500000` | variables, in the order they are written |
| stack | `00700000` to `00800000` | ESP starts at the top |

Memory is flat: there are no segments, so `mov ax, @data` and `mov ds, ax` are
not needed and are rejected with a hint.

## Not supported

`INVOKE`, `.IF` and the other high-level directives, `MACRO`, `STRUCT`, `LOCAL`,
`PROC USES`, 64-bit and floating-point data (`DQ`, `REAL4`), and jumps to `$+n`.
The assembler names the construct and suggests what to write instead.

## Intel/NASM style

Tick **Use Intel/NASM syntax** in the New dialog, or use Assembler > Intel/NASM
syntax. In this style:

- `section .data` and `section .text` replace `.data` and `.code`;
- `global _start` is accepted; the program starts at `_start` or `main`;
- a variable name is its address: `mov edx, text` loads the address, and
  `mov eax, [count]` reads memory;
- give the size when no register shows it: `mov dword [count], 5`;
- `times 10 db 0`, `resb 10`, `resw`, `resd` and `equ` work.
