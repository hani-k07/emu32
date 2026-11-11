; Recursion, stack parameters and USES
INCLUDE Irvine32.inc

.data
result DWORD ?

.code
main PROC
    push 6
    call Factorial
    mov  result, eax
    call WriteDec
    call Crlf

    mov  eax, 3
    mov  ebx, 4
    call SumSquares
    call WriteDec
    call Crlf

    INVOKE AddThree, 1, 2, 3
    call WriteDec
    call Crlf
    exit
main ENDP

Factorial PROC
    push ebp
    mov  ebp, esp
    mov  eax, [ebp+8]
    cmp  eax, 0
    ja   L1
    mov  eax, 1
    jmp  L2
L1: dec  eax
    push eax
    call Factorial
    mov  ebx, [ebp+8]
    mul  ebx
L2: pop  ebp
    ret  4
Factorial ENDP

SumSquares PROC USES ebx ecx
    mov  ecx, eax
    imul ecx, ecx
    imul ebx, ebx
    lea  eax, [ecx+ebx]
    ret
SumSquares ENDP

AddThree PROC, a:DWORD, b:DWORD, c:DWORD
    mov eax, a
    add eax, b
    add eax, c
    ret
AddThree ENDP
END main
