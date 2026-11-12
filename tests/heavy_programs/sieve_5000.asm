INCLUDE Irvine32.inc
.data
sv BYTE 5001 DUP(1)
.code
main PROC
    mov esi,OFFSET sv
    mov ecx,2
outer:
    mov eax,ecx
    mul ecx
    cmp eax,5000
    ja counting
    cmp BYTE PTR [esi+ecx],0
    je nxt
    mov edx,eax
inner:
    mov BYTE PTR [esi+edx],0
    add edx,ecx
    cmp edx,5000
    jbe inner
nxt:
    inc ecx
    jmp outer
counting:
    mov ecx,2
    mov ebx,0
cnt:
    cmp ecx,5000
    ja done
    cmp BYTE PTR [esi+ecx],0
    je s2
    inc ebx
s2:
    inc ecx
    jmp cnt
done:
    mov eax,ebx
    call WriteDec
    call Crlf
    exit
main ENDP
END main
