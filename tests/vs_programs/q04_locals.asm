; LOCAL variables and arrays, ENTER/LEAVE, nested calls and recursion (Fibonacci)
INCLUDE Irvine32.inc

.code
main PROC
    mov  ecx, 10
    mov  ebx, 0
next:
    push ebx
    call Fib
    call WriteDec
    mov  al, ' '
    call WriteChar
    inc  ebx
    loop next
    call Crlf

    call Reverse
    call Crlf

    push 3
    push 4
    call Product
    call WriteDec
    call Crlf
    exit
main ENDP

Fib PROC USES ebx
    LOCAL n:DWORD
    mov  eax, [ebp+8]
    mov  n, eax
    .IF n < 2
        ret 4
    .ENDIF
    mov  ebx, n
    dec  ebx
    push ebx
    call Fib
    push eax
    dec  ebx
    push ebx
    call Fib
    pop  ebx
    add  eax, ebx
    ret  4
Fib ENDP

Reverse PROC
    LOCAL buffer[5]:BYTE
    lea  edi, buffer
    mov  ecx, 5
    mov  al, 'a'
fill:
    mov  [edi], al
    inc  al
    inc  edi
    loop fill
    mov  ecx, 5
show:
    dec  edi
    mov  al, [edi]
    call WriteChar
    loop show
    ret
Reverse ENDP

Product PROC
    enter 0, 0
    mov  eax, [ebp+8]
    imul eax, [ebp+12]
    leave
    ret  8
Product ENDP
END main
