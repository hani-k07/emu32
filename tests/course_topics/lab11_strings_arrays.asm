; Course topic: string instructions and two-dimensional arrays.
INCLUDE Irvine32.inc

.data
source  DWORD 10, 20, 30, 40
target  DWORD LENGTHOF source DUP(0)
word1   BYTE "apple", 0
word2   BYTE "apply", 0
title1  BYTE "assembly", 0
grid    BYTE  1,  2,  3,  4            ; a 3 x 4 table, one row per line
RowSize = ($ - grid)
        BYTE  5,  6,  7,  8
        BYTE  9, 10, 11, 12

.code
main PROC
    ; Copy four dwords with one instruction
    cld
    mov   esi, OFFSET source
    mov   edi, OFFSET target
    mov   ecx, LENGTHOF source
    rep   movsd
    mov   eax, target+12
    call  WriteDec              ; 40
    call  Crlf

    ; Compare two strings until they differ
    mov   esi, OFFSET word1
    mov   edi, OFFSET word2
    mov   ecx, SIZEOF word1
    repe  cmpsb
    mov   eax, SIZEOF word1
    sub   eax, ecx              ; position of the first difference, counting from 1
    call  WriteDec              ; 5
    call  Crlf

    ; Find a character with SCASB
    mov   edi, OFFSET title1
    mov   al, 'm'
    mov   ecx, LENGTHOF title1
    repne scasb
    mov   eax, edi
    sub   eax, OFFSET title1    ; EDI stops one past the match
    call  WriteDec              ; 5
    call  Crlf

    ; Library string procedures
    INVOKE Str_length, ADDR title1
    call  WriteDec              ; 8
    call  Crlf
    INVOKE Str_ucase, ADDR title1
    mov   edx, OFFSET title1
    call  WriteString           ; ASSEMBLY
    call  Crlf

    ; Sum of the second row: base (row) plus index (column)
    mov   ebx, RowSize * 1
    mov   esi, 0
    mov   eax, 0
    mov   ecx, RowSize
row:
    movzx edx, grid[ebx + esi]
    add   eax, edx
    inc   esi
    loop  row
    call  WriteDec              ; 26
    call  Crlf
    exit
main ENDP
END main
