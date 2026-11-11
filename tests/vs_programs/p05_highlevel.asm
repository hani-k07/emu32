; MASM decision directives: .IF, .ELSEIF, .WHILE, .REPEAT
INCLUDE Irvine32.inc

.data
count DWORD 0
val   SDWORD -4

.code
main PROC
    mov eax, 7
    .IF eax > 5 && eax < 10
        mWrite "between"
    .ELSEIF eax == 5
        mWrite "five"
    .ELSE
        mWrite "outside"
    .ENDIF
    call Crlf

    mov ecx, 0
    .WHILE ecx < 5
        inc ecx
        add count, ecx
    .ENDW
    mov eax, count
    call WriteDec
    call Crlf

    mov eax, 1
    .REPEAT
        shl eax, 1
    .UNTIL eax >= 64
    call WriteDec
    call Crlf

    .IF val < 0
        mWrite "negative"
    .ENDIF
    call Crlf
    exit
main ENDP
END main
