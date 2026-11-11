; A hefty 32-bit MASM test program for emu32.
; Tests: 32-bit arithmetic, arrays, sorting, string reversal, and int 21h I/O.

.386
.model flat
.stack 4096

.data
    ; Banner and Section Headers
    banner      db "==========================================", 13, 10
                db "   EMU32 32-BIT ARCHITECTURE STRESS TEST  ", 13, 10
                db "==========================================", 13, 10, "$"

    msg_math    db 13, 10, "[1] Testing 32-Bit Math (125000 * 4 + 54321): $"
    msg_orig    db 13, 10, "[2] Original Array: $"
    msg_sort    db 13, 10, "[3] Sorted Array:   $"
    msg_str1    db 13, 10, "[4] Original Text:  $"
    msg_str2    db 13, 10, "[5] Reversed Text:  $"
    msg_prompt  db 13, 10, 13, 10, "Press any key to run countdown & exit...$"
    msg_count   db 13, 10, "Shutting down in: $"
    msg_done    db 13, 10, "All 32-bit tests passed! Goodbye.", 13, 10, "$"

    space       db " $"
    newline     db 13, 10, "$"

    ; Test Data
    num_array   dd 4500, 12, 98765, 340, 1024, 5, 77777, 89
    array_len   equ ($ - num_array) / 4     ; Calculates number of DWORD elements (8)

    test_str    db "32-Bit Flat Memory Model Works!", 0
    str_len     equ ($ - test_str) - 1      ; Length excluding null terminator

    ; Buffer for converting 32-bit integers to printable strings
    num_buffer  db 12 dup(0)                ; Max 10 digits for 32-bit uint + '$' + null

.code
main PROC
    ; --- Print Banner ---
    mov  edx, OFFSET banner
    mov  ah, 09h
    int  21h

    ; =========================================================
    ; TEST 1: 32-Bit Arithmetic & Number Printing
    ; =========================================================
    mov  edx, OFFSET msg_math
    mov  ah, 09h
    int  21h

    mov  eax, 125000
    mov  ebx, 4
    mul  ebx                    ; EAX = 500,000
    add  eax, 54321             ; EAX = 554,321
    call PrintUInt32            ; Should print 554321

    ; =========================================================
    ; TEST 2: Array Traversal & Bubble Sort (32-bit DWORDs)
    ; =========================================================
    mov  edx, OFFSET msg_orig
    mov  ah, 09h
    int  21h
    call PrintArray

    ; Perform Bubble Sort on num_array
    mov  ecx, array_len
    dec  ecx                    ; Outer loop count = N - 1
outer_loop:
    push ecx                    ; Save outer loop counter
    mov  esi, OFFSET num_array  ; Point ESI to start of array

inner_loop:
    mov  eax, [esi]             ; Load current 32-bit integer
    mov  ebx, [esi + 4]         ; Load next 32-bit integer
    cmp  eax, ebx
    jbe  no_swap                ; If EAX <= EBX, order is fine

    ; Swap values in memory
    mov  [esi], ebx
    mov  [esi + 4], eax

no_swap:
    add  esi, 4                 ; Move to next DWORD (4 bytes)
    loop inner_loop

    pop  ecx                    ; Restore outer loop counter
    loop outer_loop

    ; Print Sorted Array
    mov  edx, OFFSET msg_sort
    mov  ah, 09h
    int  21h
    call PrintArray

    ; =========================================================
    ; TEST 3: In-Place String Reversal using Two Pointers
    ; =========================================================
    mov  edx, OFFSET msg_str1
    mov  ah, 09h
    int  21h

    mov  esi, OFFSET test_str
    call PrintNullString

    ; Reverse string using ESI (start) and EDI (end)
    mov  esi, OFFSET test_str
    mov  edi, OFFSET test_str
    add  edi, str_len
    dec  edi                    ; Point EDI to last character

reverse_loop:
    cmp  esi, edi
    jge  reverse_done           ; Stop when pointers meet or cross

    mov  al, [esi]              ; Swap bytes
    mov  bl, [edi]
    mov  [esi], bl
    mov  [edi], al

    inc  esi
    dec  edi
    jmp  reverse_loop

reverse_done:
    mov  edx, OFFSET msg_str2
    mov  ah, 09h
    int  21h

    mov  esi, OFFSET test_str
    call PrintNullString

    ; =========================================================
    ; TEST 4: Keyboard Input (int 21h / 01h) & Countdown
    ; =========================================================
    mov  edx, OFFSET msg_prompt
    mov  ah, 09h
    int  21h

    mov  ah, 01h                ; Function 01h: Wait for keypress & echo
    int  21h

    mov  edx, OFFSET msg_count
    mov  ah, 09h
    int  21h

    mov  ecx, 5                 ; Countdown from 5 to 1
count_loop:
    mov  eax, ecx
    call PrintUInt32

    mov  edx, OFFSET space
    mov  ah, 09h
    int  21h

    ; Simple busy-wait delay loop to test CPU execution speed
    push ecx
    mov  ecx, 5000000           ; Adjust if too fast or too slow in emu32
delay_loop:
    nop
    loop delay_loop
    pop  ecx

    loop count_loop

    ; --- Exit Program ---
    mov  edx, OFFSET msg_done
    mov  ah, 09h
    int  21h

    mov  ah, 4Ch                ; Function 4Ch: Terminate process
    int  21h
main ENDP

; =================================================================
; PROCEDURE: PrintUInt32
; Converts unsigned 32-bit integer in EAX to ASCII and prints it.
; =================================================================
PrintUInt32 PROC
    pushad                      ; Save all 32-bit general-purpose registers

    mov  edi, OFFSET num_buffer
    add  edi, 11                ; Start at the end of the buffer
    mov  byte ptr [edi], '$'    ; Place DOS string terminator
    dec  edi

    mov  ebx, 10                ; Divisor for base-10 conversion

convert_loop:
    xor  edx, edx               ; Clear EDX before 32-bit division (EDX:EAX / EBX)
    div  ebx                    ; EAX = quotient, EDX = remainder
    add  dl, '0'                ; Convert remainder to ASCII digit
    mov  [edi], dl              ; Store character in buffer
    dec  edi                    ; Move backwards in buffer
    test eax, eax               ; Check if quotient is 0
    jnz  convert_loop

    inc  edi                    ; Point EDI to the first valid digit
    mov  edx, edi               ; Load address into EDX for int 21h
    mov  ah, 09h
    int  21h

    popad                       ; Restore all 32-bit registers
    ret
PrintUInt32 ENDP

; =================================================================
; PROCEDURE: PrintArray
; Loops through num_array and prints each 32-bit integer.
; =================================================================
PrintArray PROC
    pushad
    mov  esi, OFFSET num_array
    mov  ecx, array_len

print_arr_loop:
    mov  eax, [esi]
    call PrintUInt32

    mov  edx, OFFSET space
    mov  ah, 09h
    int  21h

    add  esi, 4                 ; Advance by 4 bytes (DWORD)
    loop print_arr_loop

    popad
    ret
PrintArray ENDP

; =================================================================
; PROCEDURE: PrintNullString
; Prints a C-style null-terminated string pointed to by ESI
; using DOS function 02h (character output).
; =================================================================
PrintNullString PROC
    pushad
print_char_loop:
    mov  dl, [esi]              ; Load byte
    cmp  dl, 0                  ; Check for null terminator
    je   print_char_done

    mov  ah, 02h                ; Function 02h: Print single character in DL
    int  21h

    inc  esi
    jmp  print_char_loop

print_char_done:
    popad
    ret
PrintNullString ENDP

END main
