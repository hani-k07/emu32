; Prints two lines with int 21h, written in Intel/NASM style.
; In this style a name is an address: "mov edx, first" loads the address of
; the text, and [first] would read the memory there.
section .data
first   db 'Assembly is fun.', 13, 10, '$'
second  db 'Function 09h prints up to the dollar sign.', 13, 10, '$'

section .text
global _start
_start:
    mov  edx, first
    mov  ah, 09h                   ; function 09h: print text
    int  21h
    mov  edx, second
    int  21h                       ; AH still holds 09h
    mov  ah, 4Ch                   ; function 4Ch: end the program
    mov  al, 0                     ; exit code 0
    int  21h
