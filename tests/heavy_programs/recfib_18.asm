INCLUDE Irvine32.inc
.data

.code
main PROC
    push 18
    call rfib
    add esp,4
    call WriteDec
    call Crlf
    exit
rfib PROC
    push ebp
    mov ebp,esp
    mov eax,[ebp+8]
    cmp eax,2
    jb base
    dec eax
    push eax
    call rfib
    add esp,4
    push eax
    mov eax,[ebp+8]
    sub eax,2
    push eax
    call rfib
    add esp,4
    pop ecx
    add eax,ecx
base:
    pop ebp
    ret
rfib ENDP
main ENDP
END main
