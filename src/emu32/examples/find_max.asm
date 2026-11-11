; Finds the largest value in an array of signed numbers.
; Signed numbers need signed jumps: JG and JLE, not JA and JBE.
INCLUDE Irvine32.inc

.data
readings SDWORD -5, 12, -30, 27, 8, -1
caption  BYTE "Highest: ", 0

.code
main PROC
    mov  esi, OFFSET readings
    mov  ecx, LENGTHOF readings
    mov  eax, [esi]                ; start with the first element
check:
    cmp  [esi], eax
    jle  not_higher                ; signed compare
    mov  eax, [esi]                ; a new highest value
not_higher:
    add  esi, TYPE readings
    loop check

    mov  edx, OFFSET caption
    call WriteString
    call WriteInt                  ; WriteInt prints the sign: +27
    call Crlf
    exit
main ENDP
END main
