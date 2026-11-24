; Reads a whole line with int 21h/0Ah and greets the user by name.
; Level: Intermediate
; Byte 0 of the buffer tells DOS its size; DOS writes the count into byte 1
; and the characters from byte 2, followed by 13 (Enter).

org 100h

    mov dx, offset ask
    mov ah, 09h
    int 21h

    mov dx, offset buffer
    mov ah, 0Ah
    int 21h

    mov bl, buffer[1]          ; how many characters were typed
    mov bh, 0
    mov buffer[bx+2], '$'      ; end the name with '$' for function 09h

    mov dx, offset hello
    mov ah, 09h
    int 21h
    mov dx, offset buffer + 2  ; the name starts at byte 2
    int 21h
    mov dx, offset bang
    int 21h
    ret

ask    db 'Your name: $'
hello  db 13, 10, 'Hello, $'
bang   db '!$'
buffer db 20, ?, 20 dup(0)     ; up to 19 characters and the 13
