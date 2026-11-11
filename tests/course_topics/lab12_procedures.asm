; Course topic: advanced procedures - stack parameters, INVOKE, USES,
; LOCAL variables, recursion and labels local to a procedure.
INCLUDE Irvine32.inc

SumOf    PROTO, first:DWORD, second:DWORD, third:DWORD
ArrayMax PROTO, pArray:PTR DWORD, count:DWORD

.data
values DWORD 7, 42, 3, 19

.code
main PROC
    INVOKE SumOf, 5, 6, 7
    call  WriteDec              ; 18
    call  Crlf
    INVOKE ArrayMax, ADDR values, LENGTHOF values
    call  WriteDec              ; 42
    call  Crlf
    push  5
    call  Factorial
    call  WriteDec              ; 120
    call  Crlf
    mov   ecx, 3
    call  Squares               ; 1 4 9
    call  Crlf
    mov   eax, ecx              ; USES kept the caller's ECX
    call  WriteDec              ; 3
    call  Crlf
    exit
main ENDP

SumOf PROC, first:DWORD, second:DWORD, third:DWORD
    mov   eax, first
    add   eax, second
    add   eax, third
    ret                         ; also removes the three arguments
SumOf ENDP

ArrayMax PROC USES esi ecx, pArray:PTR DWORD, count:DWORD
    mov   esi, pArray
    mov   ecx, count
    mov   eax, [esi]
next:
    cmp   [esi], eax
    jbe   skip
    mov   eax, [esi]
skip:
    add   esi, 4
    loop  next
    ret
ArrayMax ENDP

; A stack frame written by hand
Factorial PROC
    push  ebp
    mov   ebp, esp
    mov   eax, [ebp+8]
    cmp   eax, 1
    jbe   done
    dec   eax
    push  eax
    call  Factorial
    mul   DWORD PTR [ebp+8]
done:
    pop   ebp
    ret   4
Factorial ENDP

Squares PROC USES ecx
    LOCAL counter:DWORD
    mov   counter, 1
next:                           ; ArrayMax has a label with the same name
    mov   eax, counter
    mul   eax
    call  WriteDec
    mov   al, ' '
    call  WriteChar
    inc   counter
    loop  next
    ret
Squares ENDP
END main
