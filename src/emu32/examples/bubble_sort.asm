; Sorts an array with bubble sort and prints the result.
; Each pass moves the largest remaining value to the end, so every pass
; needs one comparison less than the one before.
INCLUDE Irvine32.inc

.data
values DWORD 42, 7, 19, 3, 88, 25, 1
count = LENGTHOF values
gap    BYTE " ", 0

.code
main PROC
    mov  ecx, count - 1            ; number of passes, and comparisons in the first pass
next_pass:
    push ecx                       ; LOOP below reuses ECX; keep the pass counter
    mov  esi, OFFSET values
compare:
    mov  eax, [esi]
    cmp  eax, [esi + 4]
    jbe  in_order                  ; neighbours already in order
    xchg eax, [esi + 4]            ; swap the two neighbours
    mov  [esi], eax
in_order:
    add  esi, 4
    loop compare
    pop  ecx
    loop next_pass

    mov  esi, OFFSET values        ; print the sorted array
    mov  ecx, count
print_next:
    mov  eax, [esi]
    call WriteDec
    mov  edx, OFFSET gap
    call WriteString
    add  esi, 4
    loop print_next
    call Crlf
    exit
main ENDP
END main
