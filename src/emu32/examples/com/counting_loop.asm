; Counts from 1 to 9 with LOOP, which repeats while CX is not 0.
; Level: Basic

org 100h

    mov cx, 9                  ; LOOP counts CX down to 0
    mov bl, '1'                ; the character to print
again:
    mov dl, bl
    mov ah, 02h
    int 21h
    mov dl, ' '
    int 21h                    ; AH is still 02h
    inc bl
    loop again
    ret
