; Reads one key with int 21h/01h and prints it again with int 21h/02h.
; Level: Basic
; Run it, then click the Screen window (or the line below it) and press a key.

org 100h

    mov dx, offset prompt
    mov ah, 09h
    int 21h

    mov ah, 01h                ; read a key; it is shown, and AL gets its code
    int 21h
    mov bl, al                 ; keep it: the next calls change AL

    mov dx, offset answer
    mov ah, 09h
    int 21h

    mov dl, bl                 ; function 02h prints the character in DL
    mov ah, 02h
    int 21h
    ret

prompt db 'Press a key: $'
answer db 13, 10, 'You pressed: $'
