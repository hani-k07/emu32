; Extended addition and subtraction, SHLD/SHRD, BCD and constant expressions
INCLUDE Irvine32.inc

MASK_LOW = 0FFh AND 0Fh
FLAGS_ALL = (1 SHL 4) OR 3
NEG_ONE = NOT 0

.data
op1 QWORD 0A2B2A40674981234h
op2 QWORD 08010870000234502h
sum DWORD 3 DUP(0)
packed BYTE 35h

.code
main PROC
    mov  esi, OFFSET op1
    mov  edi, OFFSET op2
    mov  ebx, OFFSET sum
    mov  eax, [esi]
    add  eax, [edi]
    mov  [ebx], eax
    mov  eax, [esi+4]
    adc  eax, [edi+4]
    mov  [ebx+4], eax
    mov  eax, 0
    adc  eax, 0
    mov  [ebx+8], eax
    mov  eax, sum + 8
    call WriteHex
    mov  eax, sum + 4
    call WriteHex
    mov  eax, sum
    call WriteHex
    call Crlf

    mov  edx, 0
    mov  eax, 1
    sub  eax, 2
    sbb  edx, 0
    mov  eax, edx
    call WriteInt
    call Crlf

    mov  eax, 12345678h
    mov  edx, 9ABCDEF0h
    shld eax, edx, 8
    call WriteHex
    call Crlf

    mov  al, packed
    add  al, 48h
    daa
    movzx eax, al
    call WriteHex
    call Crlf

    mov  eax, MASK_LOW
    call WriteDec
    mov  al, ' '
    call WriteChar
    mov  eax, FLAGS_ALL
    call WriteDec
    mov  al, ' '
    call WriteChar
    mov  eax, NEG_ONE
    call WriteInt
    call Crlf

    mov  eax, 8 SHR 1
    call WriteDec
    call Crlf
    exit
main ENDP
END main
