INCLUDE Irvine32.inc
.data
k DWORD ?
res DWORD ?
scale REAL8 1000000.0
.code
main PROC
    finit
    fldz
    mov ecx,1000
fl:
    mov k,ecx
    fld1
    fild k
    fmul st(0),st(0)
    fdivp st(1),st(0)
    faddp st(1),st(0)
    loop fl
    fmul scale
    fistp res
    mov eax,res
    call WriteDec
    call Crlf
    exit
main ENDP
END main
