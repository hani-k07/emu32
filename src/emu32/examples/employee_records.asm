; An array of structures: total salary and the longest-serving employee.
; (Employee PTR [esi]).Field reads a field of the record ESI points to.
INCLUDE Irvine32.inc

Employee STRUCT
    EmpName BYTE 12 DUP(0)
    Years   DWORD 0
    Salary  DWORD 0
Employee ENDS

.data
staff Employee <"Ayesha", 7, 52000>, <"Bilal", 3, 41000>, <"Chen", 12, 66000>
total DWORD 0

.code
main PROC
    mov  esi, OFFSET staff
    mov  ecx, LENGTHOF staff
    mov  edi, esi                       ; longest-serving so far
next:
    mov  eax, (Employee PTR [esi]).Salary
    add  total, eax
    mov  eax, (Employee PTR [esi]).Years
    .IF eax > (Employee PTR [edi]).Years
        mov  edi, esi
    .ENDIF
    add  esi, TYPE Employee
    loop next

    mWrite "Total salary: "
    mov  eax, total
    call WriteDec
    call Crlf
    mWrite "Longest service: "
    mov  edx, edi                       ; EmpName is the first field
    call WriteString
    call Crlf
    exit
main ENDP
END main
