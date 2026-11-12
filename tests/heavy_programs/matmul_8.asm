INCLUDE Irvine32.inc
.data
A DWORD 1,3,5,0,2,4,6,1,4,6,1,3,5,0,2,4,0,2,4,6,1,3,5,0,3,5,0,2,4,6,1,3,6,1,3,5,0,2,4,6,2,4,6,1,3,5,0,2,5,0,2,4,6,1,3,5,1,3,5,0,2,4,6,1
B DWORD 2,7,3,8,4,0,5,1,3,8,4,0,5,1,6,2,4,0,5,1,6,2,7,3,5,1,6,2,7,3,8,4,6,2,7,3,8,4,0,5,7,3,8,4,0,5,1,6,8,4,0,5,1,6,2,7,0,5,1,6,2,7,3,8
total DWORD 0
trace DWORD 0
.code
main PROC
    mov esi,0
iloop:
    cmp esi,8
    jae fin
    mov edi,0
jloop:
    cmp edi,8
    jae inext
    mov ebx,0
    mov ebp,0
kL:
    cmp ebx,8
    jae kD
    mov eax,esi
    imul eax,8
    add eax,ebx
    mov eax,A[eax*4]
    mov edx,ebx
    imul edx,8
    add edx,edi
    imul eax,B[edx*4]
    add ebp,eax
    inc ebx
    jmp kL
kD:
    add total,ebp
    cmp esi,edi
    jne nt
    add trace,ebp
nt:
    inc edi
    jmp jloop
inext:
    inc esi
    jmp iloop
fin:
    mov eax,trace
    call WriteDec
    call Crlf
    mov eax,total
    call WriteDec
    call Crlf
    exit
main ENDP
END main
