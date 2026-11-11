; String primitives: MOVSB, STOSB, SCASB, CMPSB with REP prefixes
INCLUDE Irvine32.inc

.data
source  BYTE "Assembly is fun", 0
target  BYTE SIZEOF source DUP(0)
filler  BYTE 10 DUP(?), 0
same1   BYTE "ABCDE"
same2   BYTE "ABCDE"
buffer  BYTE 21 DUP(0)
prompt  BYTE "Name: ", 0
hello   BYTE "Hello, ", 0

.code
main PROC
    cld
    mov  esi, OFFSET source
    mov  edi, OFFSET target
    mov  ecx, SIZEOF source
    rep  movsb
    mov  edx, OFFSET target
    call WriteString
    call Crlf

    mov  al, '*'
    mov  edi, OFFSET filler
    mov  ecx, LENGTHOF filler - 1
    rep  stosb
    mov  edx, OFFSET filler
    call WriteString
    call Crlf

    mov  edi, OFFSET source
    mov  al, 'f'
    mov  ecx, LENGTHOF source
    repne scasb
    dec  edi
    mov  edx, edi
    call WriteString
    call Crlf

    mov  esi, OFFSET same1
    mov  edi, OFFSET same2
    mov  ecx, LENGTHOF same1
    repe cmpsb
    jne  different
    mWrite "equal"
    jmp  next
different:
    mWrite "different"
next:
    call Crlf

    mov  edx, OFFSET prompt
    call WriteString
    mov  edx, OFFSET buffer
    mov  ecx, SIZEOF buffer
    call ReadString
    mov  edx, OFFSET hello
    call WriteString
    mov  edx, OFFSET buffer
    call WriteString
    call Crlf
    INVOKE Str_length, ADDR source
    call WriteDec
    call Crlf
    exit
main ENDP
END main
