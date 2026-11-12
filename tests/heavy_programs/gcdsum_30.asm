INCLUDE Irvine32.inc
.data

.code
main PROC
    mov esi,1
    mov ebp,0
iloop:
    cmp esi,30
    ja fin
    mov edi,1
jloop:
    cmp edi,30
    ja inext
    mov eax,esi
    mov ebx,edi
g:
    mov edx,0
    div ebx
    mov eax,ebx
    mov ebx,edx
    cmp ebx,0
    jne g
    add ebp,eax
    inc edi
    jmp jloop
inext:
    inc esi
    jmp iloop
fin:
    mov eax,ebp
    call WriteDec
    call Crlf
    exit
main ENDP
END main
