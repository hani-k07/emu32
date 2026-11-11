; Floating point with the x87 FPU: REAL4/REAL8/REAL10 data, arithmetic, compare,
; integer conversion, and the course library's float routines.
INCLUDE Irvine32.inc

.data
radius   REAL8 2.5
half     REAL4 0.5
big      REAL10 1.0E+10
values   REAL8 1.5, 2.25, -0.75
count    DWORD 3
area     REAL8 ?
rounded  DWORD ?
sum      REAL8 0.0

.code
main PROC
    finit
    ; area = pi * r * r
    fldpi
    fld   radius
    fmul  st(0), st(0)
    fmul
    fst   area
    call  WriteFloat
    call  Crlf

    ; rounded to the nearest integer
    fistp rounded
    mov   eax, rounded
    call  WriteDec
    call  Crlf

    ; sum of an array
    mov   ecx, count
    mov   esi, OFFSET values
    fldz
L1: fadd  REAL8 PTR [esi]
    add   esi, TYPE values
    loop  L1
    fstp  sum
    fld   sum
    call  WriteFloat
    call  Crlf

    ; compare: is the sum greater than half?
    fld   half
    fcomip st(0), st(1)
    .IF CARRY?
        mWrite "sum > 0.5"
    .ELSE
        mWrite "sum <= 0.5"
    .ENDIF
    call  Crlf
    fstp  st(0)

    fld   big
    fsqrt
    call  WriteFloat
    call  Crlf

    mWrite "Enter a number: "
    call  ReadFloat
    fmul  st(0), st(0)
    call  WriteFloat
    call  Crlf
    call  ShowFPUStack
    exit
main ENDP
END main
