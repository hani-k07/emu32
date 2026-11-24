; Computes 1! to 8! with MUL and prints each result.
; Level: Intermediate
; MUL BX multiplies AX by BX and puts the result in DX:AX; up to 8! it fits in AX.

org 100h

    mov cx, 1                  ; n
    mov ax, 1                  ; n!
again:
    mov bx, cx
    mul bx                     ; AX = AX * n
    push ax
    push cx
    mov ax, cx
    call print_number          ; n
    mov dx, offset equals
    mov ah, 09h
    int 21h
    pop cx
    pop ax
    push ax
    push cx
    call print_number          ; n!
    mov dx, offset newline
    mov ah, 09h
    int 21h
    pop cx
    pop ax
    inc cx
    cmp cx, 8
    jbe again
    ret

print_number proc              ; prints AX in decimal; changes AX, BX, CX, DX
    mov bx, 10
    mov cx, 0
divide:
    mov dx, 0
    div bx
    push dx
    inc cx
    cmp ax, 0
    jne divide
show:
    pop dx
    add dl, '0'
    mov ah, 02h
    int 21h
    loop show
    ret
print_number endp

equals  db '! = $'
newline db 13, 10, '$'
