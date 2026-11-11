; Irvine32 string procedures and a binary search
INCLUDE Irvine32.inc

.data
string1 BYTE "hello world   ", 0
string2 BYTE 20 DUP(0)
string3 BYTE "hello world", 0
sorted  DWORD 3, 8, 15, 21, 42, 57, 90
target  DWORD 42

.code
main PROC
    INVOKE Str_trim, ADDR string1, ' '
    INVOKE Str_copy, ADDR string1, ADDR string2
    INVOKE Str_ucase, ADDR string2
    mov  edx, OFFSET string2
    call WriteString
    call Crlf

    INVOKE Str_compare, ADDR string1, ADDR string3
    .IF ZERO?
        mWrite "same"
    .ELSE
        mWrite "different"
    .ENDIF
    call Crlf

    INVOKE Str_length, ADDR string2
    call WriteDec
    call Crlf

    ; binary search for target in sorted
    mov  ebx, 0                      ; first
    mov  ecx, LENGTHOF sorted - 1    ; last
    mov  edx, target
    mov  eax, -1
    .WHILE SDWORD PTR ebx <= ecx
        mov  esi, ebx
        add  esi, ecx
        shr  esi, 1
        .IF sorted[esi*4] == edx
            mov eax, esi
            .BREAK
        .ELSEIF sorted[esi*4] < edx
            lea ebx, [esi+1]
        .ELSE
            lea ecx, [esi-1]
        .ENDIF
    .ENDW
    call WriteInt
    call Crlf
    exit
main ENDP
END main
