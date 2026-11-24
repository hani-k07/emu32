; Passes two numbers to a procedure on the stack and reads them with BP.
; Level: Intermediate
; Step into the call and watch the Stack window: [bp+4] is the last value pushed,
; [bp+6] the one before it, because CALL pushes a 2-byte return address.

org 100h

    push 7                     ; first parameter  -> [bp+6]
    push 5                     ; second parameter -> [bp+4]
    call multiply              ; AX = 7 * 5
    add sp, 4                  ; remove the two parameters

                               ; AX = 35: print it as two digits
    mov bl, 10
    div bl                     ; AL = 3 (tens), AH = 5 (ones)
    mov bh, ah
    mov dl, al
    add dl, '0'
    mov ah, 02h
    int 21h
    mov dl, bh
    add dl, '0'
    int 21h
    ret

multiply proc
    push bp
    mov bp, sp                 ; BP = SP, so the parameters have fixed offsets
    mov ax, [bp+6]
    mul word ptr [bp+4]        ; DX:AX = AX * second parameter
    pop bp
    ret
multiply endp
