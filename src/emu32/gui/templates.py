"""Starting points for a new file (spec 9.2, 12.1). COM is the default (D80)."""

COM = """; emu32 COM program
; Code starts at offset 100h. End the program with ret.

org 100h

; write your code here

ret
"""

EXE = """; emu32 EXE program
.model small
.stack 100h

.data
    ; variables here

.code
main proc
    mov ax, @data
    mov ds, ax

    ; write your code here

    mov ah, 4Ch
    int 21h
main endp
end main
"""

CONSOLE_MASM = """\
; A 32-bit console program in MASM style.
; It prints a message with int 21h and then ends.
.386
.model flat
.stack 4096

.data
message db "Hello from emu32!", 13, 10, "$"   ; text ends with $ for function 09h

.code
main PROC
    mov  edx, OFFSET message   ; EDX = address of the text
    mov  ah, 09h               ; function 09h: print text up to the $
    int  21h

    ; Write your code here.

    mov  ah, 4Ch               ; function 4Ch: end the program
    int  21h
main ENDP
END main
"""

LIBRARY_MASM = """\
; A 32-bit program that uses the built-in library routines.
; WriteString prints the text at EDX, Crlf starts a new line,
; ReadInt reads a number into EAX, WriteInt prints EAX.
INCLUDE Irvine32.inc

.data
prompt BYTE "Enter a number: ", 0
answer BYTE "Twice that is ", 0

.code
main PROC
    mov  edx, OFFSET prompt
    call WriteString
    call ReadInt               ; EAX = the number typed
    add  eax, eax              ; double it

    mov  edx, OFFSET answer
    call WriteString
    call WriteInt
    call Crlf
    exit                       ; end the program
main ENDP
END main
"""

EMPTY_MASM = """\
.data

.code
main PROC

    ret
main ENDP
END main
"""

CONSOLE_INTEL = """\
; A 32-bit console program in Intel/NASM style.
; A name stands for its address; use [name] to read memory.
section .data
message db 'Hello from emu32!', 13, 10, '$'

section .text
global _start
_start:
    mov  edx, message          ; EDX = address of the text
    mov  ah, 09h               ; function 09h: print text up to the $
    int  21h

    ; Write your code here.

    mov  ah, 4Ch               ; function 4Ch: end the program
    int  21h
"""

LIBRARY_INTEL = """\
; Intel/NASM style with the built-in library routines.
section .data
prompt db 'Enter a number: ', 0
answer db 'Twice that is ', 0

section .text
_start:
    mov  edx, prompt
    call WriteString
    call ReadInt               ; EAX = the number typed
    add  eax, eax

    mov  edx, answer
    call WriteString
    call WriteInt
    call Crlf
    call exit
"""

EMPTY_INTEL = """\
section .data

section .text
_start:

    ret
"""

TEMPLATES = {
    # COM and EXE programs are MASM style only; the dialog turns the Intel box off for them.
    ("com", False): COM,
    ("com", True): COM,
    ("exe", False): EXE,
    ("exe", True): EXE,
    ("console", False): CONSOLE_MASM,
    ("library", False): LIBRARY_MASM,
    ("empty", False): EMPTY_MASM,
    ("console", True): CONSOLE_INTEL,
    ("library", True): LIBRARY_INTEL,
    ("empty", True): EMPTY_INTEL,
}
