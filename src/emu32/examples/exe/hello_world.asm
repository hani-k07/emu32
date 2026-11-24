; An EXE program: data in .data, code in .code, and int 21h/4Ch to end.
; Level: Basic
; mov ax, @data / mov ds, ax points DS at the data. In emu32 every segment is 0,
; so it changes nothing, but the program is the same as for a DOS assembler.

.model small
.stack 100h

.data
message db 'Hello from an EXE program!', 13, 10, '$'

.code
main proc
    mov ax, @data
    mov ds, ax

    mov dx, offset message
    mov ah, 09h
    int 21h

    mov ah, 4Ch                ; end the program
    int 21h
main endp
end main
