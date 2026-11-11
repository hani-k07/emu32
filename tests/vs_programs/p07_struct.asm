; STRUCT, EQU, = and TEXTEQU
INCLUDE Irvine32.inc

Employee STRUCT
    IdNum    BYTE "000000000"
    LastName BYTE 30 DUP(0)
    Years    WORD 0
    Salary   DWORD 0
Employee ENDS

COUNT = 3
LIMIT EQU 100
msgText TEXTEQU <"Salary: ", 0>

.data
worker Employee <"555223333", "Jones", 5, 45000>
team   Employee COUNT DUP(<>)
label1 BYTE msgText

.code
main PROC
    mov  edx, OFFSET label1
    call WriteString
    mov  eax, worker.Salary
    call WriteDec
    call Crlf
    movzx eax, worker.Years
    call WriteDec
    call Crlf
    mov  esi, OFFSET team
    mov  (Employee PTR [esi]).Years, 9
    movzx eax, (Employee PTR [esi]).Years
    call WriteDec
    call Crlf
    mov  eax, SIZEOF Employee
    call WriteDec
    call Crlf
    mov  eax, LIMIT + COUNT
    call WriteDec
    call Crlf
    exit
main ENDP
END main
