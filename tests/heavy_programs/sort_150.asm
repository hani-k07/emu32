INCLUDE Irvine32.inc
.data
arr DWORD 150 DUP(0)
.code
main PROC
    mov esi,OFFSET arr
    mov ecx,150
    mov ebx,99
gen:
    imul ebx,1103515245
    add ebx,12345
    mov eax,ebx
    shr eax,16
    and eax,7FFFh
    mov [esi],eax
    add esi,4
    loop gen
    mov ecx,149
outer:
    push ecx
    mov esi,OFFSET arr
inner:
    mov eax,[esi]
    cmp eax,[esi+4]
    jbe ok
    xchg eax,[esi+4]
    mov [esi],eax
ok:
    add esi,4
    loop inner
    pop ecx
    loop outer
    mov esi,OFFSET arr
    mov ecx,150
    mov ebx,1
    mov edi,0
cks:
    mov eax,[esi]
    imul eax,ebx
    add edi,eax
    inc ebx
    add esi,4
    loop cks
    mov eax,arr
    call WriteDec
    call Crlf
    mov eax,arr+596
    call WriteDec
    call Crlf
    mov eax,edi
    call WriteDec
    call Crlf
    exit
main ENDP
END main
