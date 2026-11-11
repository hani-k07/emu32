; Adding two 64-bit numbers with 32-bit registers: ADD the low halves, then ADC the
; high halves so the carry from the low half is not lost. Watch CF in the Flags panel.
INCLUDE Irvine32.inc

.data
first  QWORD 00000001FFFFFFFFh
second QWORD 0000000200000001h
result QWORD ?

.code
main PROC
    mov  eax, DWORD PTR first           ; low half
    add  eax, DWORD PTR second          ; CF = 1: the low half overflowed
    mov  DWORD PTR result, eax
    mov  eax, DWORD PTR first + 4       ; high half
    adc  eax, DWORD PTR second + 4      ; adds the carry too
    mov  DWORD PTR result + 4, eax

    mWrite "Result: "
    mov  eax, DWORD PTR result + 4
    call WriteHex
    mov  eax, DWORD PTR result
    call WriteHex
    mWriteLn "h"
    exit
main ENDP
END main
