; Uses a MACRO to print text: each use is replaced by the lines inside it.
; Level: Intermediate
; Compare the Source and Disassembly windows: one line of source becomes three
; instructions.

org 100h

print macro text
    mov dx, offset text
    mov ah, 09h
    int 21h
endm

    print line1
    print line2
    ret

line1 db 'Macros save typing.', 13, 10, '$'
line2 db 'The assembler copies them in.$'
