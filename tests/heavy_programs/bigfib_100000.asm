INCLUDE Irvine32.inc
.data

.code
main PROC
    mov eax,0
    mov ebx,1
    mov ecx,100000
fb:
    mov edx,eax
    add edx,ebx
    mov eax,ebx
    mov ebx,edx
    dec ecx
    jnz fb
    call WriteDec
    call Crlf
    exit
main ENDP
END main
