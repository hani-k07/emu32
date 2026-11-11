; Course topic: library procedures, extended addition, decimal arithmetic.
INCLUDE Irvine32.inc

.data
first   DWORD 0FFFFFFFFh, 00000001h    ; 1FFFFFFFFh, lowest dword first
second  DWORD 00000001h, 00000002h     ; 200000001h
total   DWORD 3 DUP(0)
prompt  BYTE "Enter a hex number: ", 0

.code
main PROC
    ; Extended addition: add dword by dword and carry into the next
    mov   esi, OFFSET first
    mov   edi, OFFSET second
    mov   ebx, OFFSET total
    mov   ecx, LENGTHOF first
    clc
add_next:
    mov   eax, [esi]
    adc   eax, [edi]
    pushfd                      ; the ADDs below would change the carry
    mov   [ebx], eax
    add   esi, 4
    add   edi, 4
    add   ebx, 4
    popfd
    loop  add_next
    mov   eax, 0
    adc   eax, 0
    mov   [ebx], eax            ; the final carry
    mov   eax, total+8
    call  WriteHex
    mov   eax, total+4
    call  WriteHex
    mov   eax, total
    call  WriteHex              ; 000000000000000400000000
    call  Crlf

    ; Packed decimal: 35 + 48 = 83
    mov   al, 35h
    add   al, 48h               ; 7Dh, not a decimal result yet
    daa                         ; 83h
    movzx eax, al
    mov   ebx, 1
    call  WriteHexB             ; 83
    call  Crlf

    ; Unpacked (ASCII) decimal: '8' + '5' = 13
    mov   ah, 0
    mov   al, '8'
    add   al, '5'
    aaa                         ; AH = 1, AL = 3
    or    ax, 3030h             ; both digits as characters
    push  eax
    mov   al, ah
    call  WriteChar
    pop   eax
    call  WriteChar
    call  Crlf

    ; Library input: a hex number, shown in decimal and binary
    mov   edx, OFFSET prompt
    call  WriteString
    call  ReadHex
    call  WriteDec
    call  Crlf
    call  WriteBin
    call  Crlf
    exit
main ENDP
END main
