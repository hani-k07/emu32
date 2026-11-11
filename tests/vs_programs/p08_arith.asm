; Integer arithmetic, shifts and flags
INCLUDE Irvine32.inc

.data
val1 SDWORD -100
val2 SDWORD 7
big  QWORD 1234567890ABCDEFh

.code
main PROC
    mov  eax, val1
    cdq
    idiv val2
    call WriteInt
    mov  eax, edx
    call WriteInt
    call Crlf

    mov  eax, 12345678h
    rol  eax, 8
    call WriteHex
    call Crlf

    movsx eax, BYTE PTR val1
    call WriteInt
    call Crlf

    mov  eax, -8
    sar  eax, 1
    call WriteInt
    call Crlf

    mov  eax, 5
    imul eax, eax, 9
    call WriteDec
    call Crlf

    mov  eax, DWORD PTR big
    call WriteHex
    mov  eax, DWORD PTR big + 4
    call WriteHex
    call Crlf

    mov  eax, 0
    cmp  eax, 1
    setl al
    movzx eax, al
    call WriteDec
    call Crlf

    xor  ecx, ecx
    jecxz zero
    mWrite "not zero"
zero:
    mWrite "done"
    call Crlf
    call DumpRegs
    exit
main ENDP
END main
