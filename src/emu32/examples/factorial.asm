; Reads a number n and prints n! (n factorial) with a recursive procedure.
; Watch the Stack window while stepping: each call pushes n, a return
; address and the old EBP.
INCLUDE Irvine32.inc

.data
ask         BYTE "Enter a number from 0 to 12: ", 0
answer      BYTE "Factorial: ", 0
out_of_range BYTE "Please enter a number from 0 to 12.", 0

.code
main PROC
    mov  edx, OFFSET ask
    call WriteString
    call ReadInt                   ; EAX = the number typed
    cmp  eax, 12
    ja   bad_input                 ; unsigned compare: negative numbers are huge, so they fail too

    push eax                       ; pass n on the stack
    call factorial                 ; EAX = n!
    add  esp, 4                    ; remove the argument again

    mov  edx, OFFSET answer
    call WriteString
    call WriteDec
    call Crlf
    exit

bad_input:
    mov  edx, OFFSET out_of_range
    call WriteString
    call Crlf
    exit
main ENDP

; factorial: the argument n is on the stack; the result comes back in EAX.
factorial PROC
    push ebp
    mov  ebp, esp                  ; [ebp + 8] is n (above the return address)
    mov  eax, [ebp + 8]
    cmp  eax, 1
    jbe  base_case                 ; 0! and 1! are both 1

    dec  eax
    push eax
    call factorial                 ; EAX = (n - 1)!
    add  esp, 4
    mul  DWORD PTR [ebp + 8]       ; EDX:EAX = (n - 1)! * n
    jmp  finished

base_case:
    mov  eax, 1
finished:
    pop  ebp
    ret
factorial ENDP
END main
