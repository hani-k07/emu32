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
| `WriteBin` | prints EAX in binary, in groups of four bits |
| `WriteBinB` | prints EAX in binary; EBX is the size in bytes (1, 2 or 4) |
| `WriteHexB` | prints EAX in hex; EBX is the size in bytes (1, 2 or 4) |
| `ReadDec` | reads an unsigned number into EAX; CF=1 and EAX=0 if it is not one |
| `ReadHex` | reads a hex number into EAX; CF=1 and EAX=0 if it is not one |
| `ReadKey` | takes a typed character into AL without waiting; ZF=1 if there is none |
| `DumpMem` | prints memory: ESI = address, ECX = count, EBX = size of each item |
| `Clrscr` | clears the Screen window |
| `WaitMsg` | prints "Press Enter to continue..." and waits |
| `Delay` | waits EAX milliseconds |
| `Randomize` | starts the random numbers from the clock |
| `Random32` | EAX = a random 32-bit number |
| `RandomRange` | EAX = a random number from 0 to EAX - 1 |
| `IsDigit` | ZF=1 if AL is a character from '0' to '9' |
| `GetMseconds` | EAX = milliseconds since midnight |
| `ParseDecimal32` | EDX = text, ECX = its length; EAX = the unsigned number, CF=1 if invalid |
| `ParseInteger32` | the same for a signed number; OF=1 if invalid |
| `SetTextColor`, `Gotoxy` | accepted and ignored: the Screen window is plain text |

String procedures take their arguments on the stack, so call them with `INVOKE`:

| Procedure | Does |
|---|---|
| `INVOKE Str_length, ADDR s` | EAX = length of the 0-terminated string |
| `INVOKE Str_copy, ADDR source, ADDR target` | copies the string and its 0 |
| `INVOKE Str_compare, ADDR a, ADDR b` | sets the flags as `CMP a, b` would: use `je`, `jb`, `ja` |
| `INVOKE Str_ucase, ADDR s` | changes a to z into A to Z |
| `INVOKE Str_trim, ADDR s, ' '` | removes that character from the end |

## Procedures

```
AddThree PROTO, first:DWORD, second:DWORD, third:DWORD   ; optional

AddThree PROC USES ebx, first:DWORD, second:DWORD, third:DWORD
    LOCAL temp:DWORD           ; space on the stack, only inside this procedure
    mov  eax, first
    add  eax, second
    mov  temp, eax
    add  eax, third
    ret                         ; restores EBX, removes the arguments
AddThree ENDP

    INVOKE AddThree, 1, 2, 3    ; push 3, push 2, push 1, call AddThree
```

- Parameters are at `[ebp+8]`, `[ebp+12]`, ... and LOCAL variables below EBP. emu32
  writes the usual entry code (`push ebp`, `mov ebp, esp`, `sub esp, n`, then `push`
  for each `USES` register) and, at each `ret`, the matching exit code ending in
  `ret n`, which removes the arguments (the stdcall convention). Single steps show
  these instructions on the `PROC` and `ret` lines.
- `INVOKE name, args` pushes the arguments from last to first and calls. `ADDR x`
  passes the address of `x`; for a LOCAL variable it uses EAX, so EAX changes.
- Labels inside a procedure belong to that procedure, so two procedures may both use
  `next:` or `done:`. A label with two colons (`retry::`) is visible everywhere.

## Program models

| Model | Write it like this | Memory |
|---|---|---|
| COM (default) | `org 100h` ... `ret` | one 64 KB area at 0; the program starts at 100h; data stays where you write it |
| EXE | `.model small`, `.data`, `.code`, `mov ax, @data` / `mov ds, ax`, end with `int 21h/4Ch` | the same 64 KB area; `.data` at 100h, code after it |
| 32-bit flat | `.386` and `.model flat`, or `INCLUDE Irvine32.inc` | code at `00400000` (read-only), data at `00500000`, stack below `00800000` |

emu32 picks the model from the source: `org` means COM, `.model small` (or tiny,
compact, medium, large) means EXE, `.model flat`, `.386` or `INCLUDE Irvine32.inc` means
flat. A file with none of these is a COM program. `#make_com#` and `#make_exe#` lines
choose the model too.

COM and EXE programs run like an 8086: `call` and `ret` use 2-byte return addresses, so
after `push bp` / `mov bp, sp` the first parameter is `[bp+4]`; `loop` counts CX (CX = 0
means 65,536 times); `movsb`, `lodsb` and the other string instructions use SI, DI and
CX. 32-bit registers (EAX, ECX, ...) work in the same program, as on a 386. All segment
registers are 0 and `@data` is 0, so `mov ax, @data` / `mov ds, ax` changes nothing.
`ret` at the end of a COM program ends it.

PROC parameters, `LOCAL` and `INVOKE` belong to 32-bit flat programs; in COM and EXE
programs pass parameters with `push` and read them with `[bp+4]`, `[bp+6]`, ...

## int 21h services

Put the function number in AH, then write `int 21h`. In COM and EXE programs a string or
buffer address goes in DX; in 32-bit flat programs, in EDX.

| AH | Does |
|---|---|
| `01h` | reads one character into AL and shows it (Enter gives 0Dh) |
| `02h` | prints the character in DL |
| `06h` | with DL = FFh: reads a typed character into AL without waiting (ZF = 1 if none); otherwise prints DL |
| `07h`, `08h` | reads one character into AL without showing it |
| `09h` | prints the text at DX (flat: EDX), up to a `$` |
| `0Ah` | reads a line into the buffer at DX (flat: EDX): byte 0 is the buffer size, DOS puts the count in byte 1, then the characters and 0Dh |
| `2Ah` | date: CX = year, DH = month, DL = day, AL = day of the week (0 = Sunday) |
| `2Ch` | time: CH = hour, CL = minute, DH = second, DL = hundredths |
| `4Ch` | ends the program; AL is the exit code |
| `40h` | prints EDX as a signed decimal number (emu32 only, flat programs; in DOS this function writes to a file) |

`int 20h` ends the program too.

## int 10h and int 16h services

| Interrupt | AH | Does |
|---|---|---|
| `int 10h` | `0Eh` | prints the character in AL |
| `int 10h` | `00h` | sets a video mode, which clears the screen |
| `int 16h` | `00h` | waits for a key: AH = scan code, AL = character |
| `int 16h` | `01h` | checks for a key: ZF = 1 if none, else AX = the key, which stays for the next read |

Any other function stops the program with "int XXh function YYh is not supported yet".

## Decision directives

MASM writes the compares and jumps for you:

```
.IF eax > 5 && eax < 10
    mWrite "between"
.ELSEIF eax == 5
    mWrite "five"
.ELSE
    mWrite "outside"
.ENDIF

.WHILE ecx < 5          ; also .REPEAT ... .UNTIL condition
    inc ecx
    .BREAK .IF ecx == 3 ; .CONTINUE .IF works the same way
.ENDW
```

Operators: `==` `!=` `<` `<=` `>` `>=`, `&&` `||` `!` and parentheses, and the
flags `CARRY?` `ZERO?` `SIGN?` `OVERFLOW?` `PARITY?`. A compare is signed when an
operand is a signed variable (`SDWORD`, `SWORD`, `SBYTE`) or uses `SDWORD PTR`;
registers and other variables compare unsigned, as in MASM.

## Macros

```
mPrint MACRO value, times:=<1>   ; a default value; value:REQ makes it required
    LOCAL again                  ; a label that is new in each use
    mov ecx, times
again:
    mWrite value
    loop again
ENDM
```

The course macros `mWrite`, `mWriteLn`, `mWriteString`, `mWriteSpace`,
`mReadString`, `mGotoxy` and `mDumpMem` are built in; `INCLUDE Macros.inc` is
accepted and not needed. `name TEXTEQU <text>` and `name EQU <text>` replace a name
with text.

## Structures

```
Employee STRUCT
    Id     BYTE "000000000"
    Years  WORD 0
    Salary DWORD 0
Employee ENDS

.data
worker Employee <"555223333", 5, 45000>
team   Employee 3 DUP(<>)
```

Use `worker.Salary`, `(Employee PTR [esi]).Years`, `Employee.Years` (the field
offset), `SIZEOF Employee` and `TYPE team`.

## More data directives

`QWORD` (or `DQ`) holds 64-bit values; read them a dword at a time with
`DWORD PTR big` and `DWORD PTR big + 4`. `name LABEL type` gives the data that
follows a second name and size. `ALIGN 4` pads the data to a multiple of 4.
Anonymous labels: `@@:` with `jmp @F` (the next one) and `jmp @B` (the previous one).
Constant expressions may use `+ - * / MOD`, `AND OR XOR NOT` and `SHL SHR`; use
parentheses when mixing shifts with `+` or `-`.

## Floating point (x87 FPU)

```
.data
radius REAL8 2.5            ; also REAL4 (single) and REAL10 (extended)
area   REAL8 ?
.code
    finit
    fldpi                   ; ST(0) = pi
    fld    radius
    fmul   st(0), st(0)     ; r * r
    fmul                    ; pi * r * r
    fstp   area
    fld    area
    call   WriteFloat       ; +1.9634954E+001
```

`WriteFloat` prints ST(0) in scientific notation and leaves it on the stack;
`ReadFloat` reads a number and pushes it (text that is not a number pushes 0.0
and sets OF); `ShowFPUStack` prints ST(0) to ST(7). `REAL8 PTR [esi]` reads a
REAL8 through a pointer. The FPU starts as in a Windows program: every register
empty, 53-bit precision. The **FPU** panel shows the register stack and the
status word while you step; step back restores it too.

## Conditional assembly and repeat blocks

These run while the program is assembled, not while it runs:

```
DEBUG = 1
IF DEBUG                  ; also IFE, IFB <arg>, IFNB <arg>, IFIDN <a>, <b>,
    call DumpRegs         ; IFIDNI, IFDIF, IFDEF name, IFNDEF, ELSEIF, ELSE
ENDIF

REPT 3                    ; the lines, 3 times
    inc eax
ENDM
FOR reg, <eax, ebx, ecx>  ; once per item; FORC goes through characters
    push reg
ENDM
n = 1
WHILE n LE 5              ; as long as the constant expression is true
    DWORD n * n
    n = n + 1
ENDM
```

`EQ NE LT LE GT GE` compare constants. `EXITM` leaves a macro early. Text in angle
brackets is read without case, like names.

## Not supported

Programs split over several files (`EXTERN`) and jumps to `$+n`. The assembler
names the construct and suggests what to write instead.

## Intel/NASM style

Tick **Use Intel/NASM syntax** in the New dialog, or use Assembler > Intel/NASM
syntax. In this style:

- `section .data` and `section .text` replace `.data` and `.code`;
- `global _start` is accepted; the program starts at `_start` or `main`;
- a variable name is its address: `mov edx, text` loads the address, and
  `mov eax, [count]` reads memory;
- give the size when no register shows it: `mov dword [count], 5`;
- `times 10 db 0`, `resb 10`, `resw`, `resd` and `equ` work.
