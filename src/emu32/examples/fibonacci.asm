; Prints the first 12 Fibonacci numbers.
; Intel/NASM style with the built-in library routines.
; Each number is the sum of the two before it: 0, 1, 1, 2, 3, 5, ...
section .data
heading db 'Fibonacci numbers:', 0
gap     db ' ', 0

section .text
_start:
    mov  edx, heading
    call WriteString
    call Crlf
    mov  ecx, 12                   ; how many numbers to print
    mov  eax, 0                    ; the current number
    mov  ebx, 1                    ; the next number
next:
    call WriteDec                  ; prints EAX
    mov  edx, gap
    call WriteString
    mov  edx, eax
    add  edx, ebx                  ; EDX = current + next
    mov  eax, ebx                  ; move one step along the sequence
    mov  ebx, edx
    loop next
    call Crlf
    call exit
