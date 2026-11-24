; Prints a message with int 21h, function 09h.
; Level: Basic
; A COM program starts at offset 100h and ends with ret.

org 100h

    mov dx, offset message     ; DX = address of the text
    mov ah, 09h                ; function 09h: print text up to the '$'
    int 21h
    ret                        ; back to DOS: the program ends

message db 'Hello, world!', 13, 10, '$'   ; 13, 10 = carriage return, line feed
