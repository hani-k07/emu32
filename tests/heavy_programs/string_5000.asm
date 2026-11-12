INCLUDE Irvine32.inc
.data
buf BYTE 5000 DUP(0)
.code
main PROC
    mov esi,OFFSET buf
    mov ecx,0
fill:
    cmp ecx,5000
    jae scan
    mov eax,ecx
    mov edx,0
    mov ebx,26
    div ebx
    add dl,97
    mov [esi+ecx],dl
    inc ecx
    jmp fill
scan:
    mov ecx,0
    mov ebx,0
    mov edi,0
sl:
    cmp ecx,5000
    jae fin
    movzx eax,BYTE PTR [esi+ecx]
    cmp al,'e'
    jne nc
    inc ebx
nc:
    push eax
    mov eax,ecx
    mov edx,0
    push ebx
    mov ebx,251
    div ebx
    pop ebx
    inc edx
    pop eax
    imul eax,edx
    add edi,eax
    inc ecx
    jmp sl
fin:
    mov eax,ebx
    call WriteDec
    call Crlf
    mov eax,edi
    call WriteDec
    call Crlf
    exit
main ENDP
END main
