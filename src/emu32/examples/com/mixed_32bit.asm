; A 16-bit program that uses 32-bit registers for a multiplication too big for AX.
; Level: Intermediate
; 1000 * 3000 = 3,000,000 does not fit in 16 bits. EAX and EBX hold 32 bits, as on a
; 386; the Registers panel shows them in the 32-bit column.

org 100h

    mov eax, 1000
    mov ebx, 3000
    mul ebx                    ; EDX:EAX = EAX * EBX
    mov result, eax

    mov dx, offset text
    mov ah, 09h
    int 21h

    mov eax, result            ; print EAX in decimal with 32-bit division
    mov ebx, 10
    mov cx, 0
divide:
    mov edx, 0
    div ebx                    ; EAX = EAX / 10, EDX = last digit
    push dx
    inc cx
    cmp eax, 0
    jne divide
show:
    pop dx
    add dl, '0'
    mov ah, 02h
    int 21h
    loop show
    ret

result dd ?
text   db '1000 * 3000 = $'
