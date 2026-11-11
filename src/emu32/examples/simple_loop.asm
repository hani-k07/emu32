; Counts from 1 to 9 with LOOP and prints each digit with int 21h.
.386
.model flat

.code
main PROC
    mov  ecx, 9                    ; LOOP repeats while ECX is not zero
    mov  bl, '1'                   ; the first digit, as a character
again:
    mov  dl, bl
    mov  ah, 02h                   ; function 02h prints the character in DL
    int  21h
    mov  dl, ' '
    int  21h
    inc  bl                        ; '1' + 1 = '2', and so on
    loop again

    mov  dl, 13                    ; carriage return and line feed
    int  21h
    mov  dl, 10
    int  21h
    mov  ah, 4Ch
    int  21h
main ENDP
END main
