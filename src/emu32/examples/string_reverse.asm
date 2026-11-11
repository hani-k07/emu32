; Reverses a string with the stack and prints it with int 21h.
; Characters are pushed in order and popped in reverse order.
.386
.model flat

.data
original BYTE "stressed", 0
reversed BYTE SIZEOF original DUP('$')   ; '$' marks the end for function 09h
new_line BYTE 13, 10, '$'

.code
main PROC
    mov  esi, OFFSET original
    xor  ecx, ecx                  ; ECX counts the characters pushed
push_next:
    mov  al, [esi]
    cmp  al, 0
    je   pop_all                   ; stop at the 0 that ends the string
    push eax                       ; the stack holds dwords; AL is the low byte
    inc  esi
    inc  ecx
    jmp  push_next

pop_all:
    mov  edi, OFFSET reversed
    jecxz print                    ; an empty string has nothing to pop
pop_next:
    pop  eax
    mov  [edi], al
    inc  edi
    loop pop_next

print:
    mov  edx, OFFSET reversed
    mov  ah, 09h                   ; print up to the '$'
    int  21h
    mov  edx, OFFSET new_line
    int  21h
    mov  ah, 4Ch                   ; end the program
    int  21h
main ENDP
END main
