; Sorts an array of bytes with bubble sort, then prints it.
; Level: Intermediate
; Each pass swaps neighbors that are out of order; the biggest value moves to the end.

org 100h

    mov cx, count - 1          ; passes
outer:
    push cx
    mov si, offset values
inner:
    mov al, [si]
    cmp al, [si+1]
    jbe in_order               ; unsigned: already in order
    xchg al, [si+1]            ; swap the two bytes
    mov [si], al
in_order:
    inc si
    loop inner
    pop cx
    loop outer

    mov si, offset values      ; print each value as one digit and a space
    mov cx, count
show:
    mov dl, [si]
    add dl, '0'
    mov ah, 02h
    int 21h
    mov dl, ' '
    int 21h
    inc si
    loop show
    ret

values db 5, 2, 9, 1, 7, 3
count  equ $ - values
