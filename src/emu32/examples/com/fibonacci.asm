; Prints the first 12 Fibonacci numbers: each is the sum of the two before it.
; Level: Intermediate

org 100h

    mov ax, 0                  ; F(n)
    mov bx, 1                  ; F(n+1)
    mov cx, 12
again:
    push ax
    push bx
    push cx
    call print_number
    mov dl, ' '
    mov ah, 02h
    int 21h
    pop cx
    pop bx
    pop ax
    mov dx, ax                 ; next pair: (b, a + b)
    add dx, bx
    mov ax, bx
    mov bx, dx
    loop again
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
