; Sum an array with LENGTHOF, SIZEOF and TYPE (Irvine32 style)
INCLUDE Irvine32.inc

.data
arrayB  BYTE  10h, 20h, 30h
arrayW  WORD  100h, 200h, 300h, 400h
arrayD  DWORD 10000h, 20000h, 30000h
signed  SDWORD -5, 7, -12
msg     BYTE "Sum = ", 0
sizes   BYTE "Sizes: ", 0
total   DWORD ?

.code
main PROC
    mov  esi, OFFSET arrayD
    mov  ecx, LENGTHOF arrayD
    mov  eax, 0
L1: add  eax, [esi]
    add  esi, TYPE arrayD
    loop L1
    mov  total, eax
    mov  edx, OFFSET msg
    call WriteString
    call WriteHex
    call Crlf

    mov  edx, OFFSET sizes
    call WriteString
    mov  eax, SIZEOF arrayW
    call WriteDec
    mov  al, ' '
    call WriteChar
    mov  eax, LENGTHOF arrayB
    call WriteDec
    mov  al, ' '
    call WriteChar
    mov  eax, TYPE arrayW
    call WriteDec
    call Crlf

    mov  eax, signed + 4
    add  eax, signed
    call WriteInt
    call Crlf
    exit
main ENDP
END main
