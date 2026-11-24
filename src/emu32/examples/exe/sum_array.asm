; Adds an array of words in an EXE program and prints the sum.
; Level: Basic
; LENGTHOF gives the number of elements; SI indexes the array.

.model small
.stack 100h

.data
numbers dw 100, 200, 300, 400
label1  db 'Sum: $'

.code
main proc
    mov ax, @data
    mov ds, ax

    mov si, 0
    mov ax, 0
    mov cx, lengthof numbers
add_next:
    add ax, numbers[si]
    add si, 2
    loop add_next

    push ax
    mov dx, offset label1
    mov ah, 09h
    int 21h
    pop ax

    mov bx, 10                 ; print AX in decimal
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

    mov ah, 4Ch
    int 21h
main endp
end main
