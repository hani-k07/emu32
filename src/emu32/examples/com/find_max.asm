; Finds the largest signed number in an array with CMP and JG.
; Level: Basic
; JG compares signed numbers, so -5 is smaller than 3. Try JA instead and see the
; difference: -5 is FFFBh, a large unsigned number.

org 100h

    mov si, offset numbers
    mov ax, [si]               ; the first number is the largest so far
    mov cx, count - 1
check:
    add si, 2
    cmp [si], ax
    jle not_bigger
    mov ax, [si]
not_bigger:
    loop check

    mov largest, ax
    mov dx, offset text
    mov ah, 09h
    int 21h
    mov ax, largest            ; at most 99 here: two digits
    mov bl, 10
    div bl
    mov bh, ah
    mov dl, al
    add dl, '0'
    mov ah, 02h
    int 21h
    mov dl, bh
    add dl, '0'
    int 21h
    ret

numbers dw 3, -5, 42, 17, -20, 8
count   equ ($ - numbers) / 2
largest dw ?
text    db 'Largest: $'
