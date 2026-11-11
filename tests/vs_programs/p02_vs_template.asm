; The Visual Studio console template without a library
.386
.model flat, stdcall
.stack 4096
ExitProcess PROTO, dwExitCode:DWORD

.data
sum DWORD 0
firstVal  DWORD 20002000h
secondVal DWORD 11111111h

.code
main PROC
    mov  eax, firstVal
    add  eax, secondVal
    mov  sum, eax
    INVOKE ExitProcess, 0
main ENDP
END main
