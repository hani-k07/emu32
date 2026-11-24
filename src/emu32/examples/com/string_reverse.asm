; Reverses a string: LODSB reads it forward, and DI fills the result from the end.
; Level: Intermediate
; SI moves forward through the text, DI moves backward through the result.

org 100h

    mov si, offset text
    mov di, offset result + text_len - 1   ; last character of the result
    mov cx, text_len
    cld                        ; LODSB goes forward (SI = SI + 1)
copy:
    lodsb                      ; AL = [SI], SI = SI + 1
    mov [di], al
    dec di
    loop copy

    mov dx, offset result
    mov ah, 09h
    int 21h
    ret

text   db 'stressed'
text_len equ $ - text
result db text_len dup('?'), '$'
