; Two-dimensional table and scaled indexes
INCLUDE Irvine32.inc

.data
table  DWORD 1, 2, 3, 4
       DWORD 5, 6, 7, 8
       DWORD 9, 10, 11, 12
RowSize = 4 * TYPE table
words  WORD 10, 20, 30, 40

.code
main PROC
    mov  ebx, RowSize * 2
    mov  esi, 1
    mov  eax, table[ebx + esi*TYPE table]
    call WriteDec
    call Crlf

    mov  esi, 3
    movzx eax, words[esi*TYPE words]
    call WriteDec
    call Crlf

    mov  eax, [table + 8]
    call WriteDec
    call Crlf

    mov  esi, OFFSET table
    mov  eax, [esi + 4*11]
    call WriteDec
    call Crlf
    exit
main ENDP
END main
