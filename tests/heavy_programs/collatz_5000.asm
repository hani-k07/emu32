INCLUDE Irvine32.inc
.data

.code
main PROC
    mov esi,1
    mov edi,0
nextn:
    cmp esi,5000
    ja fin
    mov eax,esi
c1:
    cmp eax,1
    je endc
    test eax,1
    jz ev
    lea eax,[eax+eax*2+1]
    jmp stp
ev:
    shr eax,1
stp:
    inc edi
    jmp c1
endc:
    inc esi
    jmp nextn
fin:
    mov eax,edi
    call WriteDec
    call Crlf
    exit
main ENDP
END main
