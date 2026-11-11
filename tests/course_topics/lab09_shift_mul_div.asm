; Course topic: shift, rotate, MUL and DIV instructions.
INCLUDE Irvine32.inc

.code
main PROC
    ; Multiply by shifting: 13 * 10 = 13 * 8 + 13 * 2
    mov   eax, 13
    mov   ebx, eax
    shl   eax, 3
    shl   ebx, 1
    add   eax, ebx
    call  WriteDec              ; 130
    call  Crlf

    ; Rotate the two halves of a byte
    mov   al, 0F0h
    rol   al, 4                 ; 0Fh
    movzx eax, al
    mov   ebx, 1                ; show one byte
    call  WriteBinB             ; 0000 1111
    call  Crlf

    ; A 64-bit product: MUL puts the high half in EDX
    mov   eax, 12345678h
    mov   ebx, 100h
    mul   ebx
    xchg  eax, edx
    call  WriteHex              ; 00000012 (high half)
    mov   eax, edx
    call  WriteHex              ; 34567800 (low half)
    call  Crlf

    ; Signed division rounds toward zero: -50 / 7 = -7, remainder -1
    mov   eax, -50
    cdq
    mov   ebx, 7
    idiv  ebx
    call  WriteInt
    mov   al, ' '
    call  WriteChar
    mov   eax, edx
    call  WriteInt
    call  Crlf

    ; SHRD shifts a 64-bit value in EDX:EAX right by 4
    mov   edx, 1
    mov   eax, 0
    shrd  eax, edx, 4
    shr   edx, 4
    call  WriteHex              ; 10000000
    call  Crlf
    exit
main ENDP
END main
