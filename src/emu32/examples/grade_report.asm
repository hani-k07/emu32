; Letter grades with MASM's decision directives: .IF, .ELSEIF, .ELSE and .WHILE.
; MASM turns each condition into CMP and conditional jumps; step through it in the
; emulator and watch the Disassembly panel to see the instructions it made.
INCLUDE Irvine32.inc

.data
scores  DWORD 91, 78, 85, 52, 67, 100
passed  DWORD 0

.code
main PROC
    mov  esi, 0                         ; index of the current score
    .WHILE esi < LENGTHOF scores
        mov  eax, scores[esi*TYPE scores]
        call WriteDec
        mWrite " -> "
        .IF eax >= 90
            mWrite "A"
        .ELSEIF eax >= 80
            mWrite "B"
        .ELSEIF eax >= 70
            mWrite "C"
        .ELSEIF eax >= 60
            mWrite "D"
        .ELSE
            mWrite "F"
        .ENDIF
        .IF eax >= 60
            inc  passed
        .ENDIF
        call Crlf
        inc  esi
    .ENDW

    mWrite "Passed: "
    mov  eax, passed
    call WriteDec
    mWrite " of "
    mov  eax, LENGTHOF scores
    call WriteDec
    call Crlf
    exit
main ENDP
END main
