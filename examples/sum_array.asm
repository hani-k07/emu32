; Adds up the numbers in an array.
; The result ends up in EAX and in the variable total.
.386
.model flat, stdcall
.stack 4096

.data
numbers DWORD 12, 7, 30, 1, 50     ; the values to add
total   DWORD ?                    ; the sum is stored here

.code
main PROC
    mov  esi, OFFSET numbers       ; ESI points at the first element
    mov  ecx, LENGTHOF numbers     ; ECX counts the elements left
    xor  eax, eax                  ; EAX holds the running sum
add_next:
    add  eax, [esi]                ; add the current element
    add  esi, TYPE numbers         ; move to the next element (4 bytes)
    loop add_next                  ; ECX = ECX - 1, repeat while ECX is not 0
    mov  total, eax                ; keep the result in memory too
    ret
main ENDP
END main
