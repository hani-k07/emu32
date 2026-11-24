; Adds the numbers in an array and prints the sum in decimal.
; Level: Basic
; Watch BX walk through the array in the Memory window while stepping.

org 100h

    mov bx, offset numbers     ; BX points at the first number
    mov cx, count              ; how many numbers
    mov ax, 0                  ; the running sum
next:
    add ax, [bx]               ; add one word
    add bx, 2                  ; a word is 2 bytes
    loop next                  ; CX = CX - 1, repeat until CX is 0

    push ax
    mov dx, offset sum_text
    mov ah, 09h
    int 21h
    pop ax
    call print_number
    ret

; Prints AX as an unsigned decimal number.
print_number proc
    mov bx, 10
    mov cx, 0                  ; number of digits
divide:
    mov dx, 0
    div bx                     ; AX = AX / 10, DX = the last digit
    push dx                    ; digits come out backwards: keep them on the stack
    inc cx
    cmp ax, 0
    jne divide
show:
    pop dx
    add dl, '0'                ; digit 7 becomes the character '7'
    mov ah, 02h
    int 21h
    loop show
    ret
print_number endp

numbers dw 12, 25, 7, 31, 25
count   equ ($ - numbers) / 2  ; bytes / 2 = number of words
sum_text db 'Sum: $'
