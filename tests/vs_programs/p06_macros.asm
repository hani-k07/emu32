; User macros with parameters and LOCAL labels
INCLUDE Irvine32.inc

mPrintNum MACRO value
    push eax
    mov  eax, value
    call WriteDec
    call Crlf
    pop  eax
ENDM

mMax MACRO dest, a, b
    LOCAL done
    mov  dest, a
    cmp  dest, b
    jge  done
    mov  dest, b
done:
ENDM

.data
x DWORD 42

.code
main PROC
    mPrintNum x
    mPrintNum 7
    mMax eax, 3, 9
    call WriteDec
    call Crlf
    mMax ebx, 12, 5
    mov  eax, ebx
    call WriteDec
    call Crlf
    exit
main ENDP
END main
