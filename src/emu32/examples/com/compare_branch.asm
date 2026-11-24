; Compares two numbers with CMP and chooses a message with JE, JA and JMP.
; Level: Basic
; Change the values of first and second, compile again and watch which jump is taken.

org 100h

    mov ax, first
    cmp ax, second             ; sets the flags as if computing AX - second
    je  same                   ; ZF = 1: equal
    ja  bigger                 ; unsigned: AX > second
    mov dx, offset smaller_text
    jmp show
same:
    mov dx, offset same_text
    jmp show
bigger:
    mov dx, offset bigger_text
show:
    mov ah, 09h
    int 21h
    ret

first  equ 42
second equ 17
same_text    db 'The numbers are equal.$'
bigger_text  db 'The first number is bigger.$'
smaller_text db 'The first number is smaller.$'
