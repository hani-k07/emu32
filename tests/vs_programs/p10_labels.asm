; Anonymous labels, LABEL directive, global labels and ALIGN
INCLUDE Irvine32.inc

.data
dwordView LABEL DWORD
wordLo WORD 5678h
wordHi WORD 1234h
ALIGN 4
value DWORD 3

.code
main PROC
    mov  eax, dwordView
    call WriteHex
    call Crlf

    mov  ecx, 3
@@: mov  eax, ecx
    call WriteDec
    loop @B
    call Crlf

    cmp  value, 3
    je   @F
    mWrite "wrong"
@@: mWrite "jumped"
    call Crlf
    call Helper
    exit
main ENDP

Helper PROC
    jmp  Outside
Helper ENDP

Back::
    ret
Outside::
    mWrite "global"
    call Crlf
    jmp Back
END main
