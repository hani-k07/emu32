; PROTO and INVOKE with pointer parameters (array sum and fill)
INCLUDE Irvine32.inc

ArraySum  PROTO, ptrArray:PTR DWORD, arraySize:DWORD
FillArray PROTO, pArray:PTR DWORD, count:DWORD, value:DWORD

.data
array DWORD 5 DUP(?)
theSum DWORD ?

.code
main PROC
    INVOKE FillArray, ADDR array, LENGTHOF array, 7
    INVOKE ArraySum, ADDR array, LENGTHOF array
    mov theSum, eax
    call WriteDec
    call Crlf
    exit
main ENDP

ArraySum PROC USES esi ecx, ptrArray:PTR DWORD, arraySize:DWORD
    mov esi, ptrArray
    mov ecx, arraySize
    mov eax, 0
    cmp ecx, 0
    je  L2
L1: add eax, [esi]
    add esi, 4
    loop L1
L2: ret
ArraySum ENDP

FillArray PROC USES edi ecx eax, pArray:PTR DWORD, count:DWORD, value:DWORD
    mov edi, pArray
    mov ecx, count
    mov eax, value
    cld
    rep stosd
    ret
FillArray ENDP
END main
