; Conditional assembly and repeat blocks: IF, IFB, IFIDN, EXITM, REPT, FOR, FORC, WHILE
INCLUDE Irvine32.inc

DEBUG = 1
TABLE_SIZE = 5

; Writes a number, then an optional separator; IFB tests for a missing argument.
mShowNum MACRO value, separator
    mov  eax, value
    call WriteDec
    IFNB <separator>
        mWrite separator
    ENDIF
ENDM

; Chooses the register by name; IFIDNI compares two texts.
mZero MACRO reg
    IFIDNI <reg>, <eax>
        xor eax, eax
        EXITM
    ENDIF
    mov reg, 0
ENDM

.data
squares LABEL DWORD
n = 1
WHILE n LE TABLE_SIZE
    DWORD n * n
    n = n + 1
ENDM
letters LABEL BYTE
FORC ch, <abc>
    BYTE "&ch&"
ENDM
    BYTE 0
powers LABEL DWORD
FOR p, <1, 2, 4, 8>
    DWORD p
ENDM

.code
main PROC
    mov  esi, OFFSET squares
    REPT TABLE_SIZE
        mShowNum [esi], " "
        add  esi, 4
    ENDM
    call Crlf

    mov  edx, OFFSET letters
    call WriteString
    call Crlf

    mShowNum powers + 12
    call Crlf

    mov  eax, 99
    mZero eax
    mShowNum eax, " "
    mov  ebx, 7
    mZero ebx
    mShowNum ebx
    call Crlf

    IF DEBUG
        mWrite "debug build"
    ELSE
        mWrite "release build"
    ENDIF
    call Crlf
    IF TABLE_SIZE GT 10
        mWrite "big"
    ELSEIF TABLE_SIZE EQ 5
        mWrite "five"
    ENDIF
    call Crlf
    exit
main ENDP
END main
