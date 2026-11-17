INCLUDE Irvine32.inc
.data

.code
main PROC
    mov esi,0
    mov edi,0
nl:
    cmp esi,5000
    ja fin
    mov eax,esi
pc:
    cmp eax,0
    je nx
    mov edx,eax
    and edx,1
    add edi,edx
    shr eax,1
    jmp pc
nx:
    inc esi
    jmp nl
fin:
    mov eax,edi
    call WriteDec
    call Crlf
    exit
main ENDP
END main
