# Quick start

This tutorial takes about ten minutes. You write a short program, run it one
instruction at a time, and watch what each instruction does.

## 1. Write a program

1. Choose **File > New** (Ctrl+N).
2. Pick **32-bit with library routines** and press OK. You get a small program
   that asks for a number and prints it twice as large.
3. Read the comments. Every line after `;` is a comment.

A program has two parts:

- `.data` holds variables, such as text to print.
- `.code` holds instructions. The program starts at `main` and ends at `exit`.

## 2. Compile

Press **F5** (Assembler > Compile). The Messages panel at the bottom says how
many bytes and instructions the program has.

If there is a mistake, the panel lists each error with its line number, for
example `line 12: unknown instruction 'mvo'`. Click an error to jump to the
line. Fix it and press F5 again.

## 3. Open the emulator

Press **Ctrl+F5** (Emulator > Emulate). The emulator window opens with the
program loaded. It shows:

- **Registers**: EAX, EBX, ECX, EDX and the others, in hex. AX, AH and AL are
  the lower parts of EAX.
- **Memory**: one byte per row, in hex, decimal and as a character.
- **Disassembly**: the instructions in memory. `>` marks the next one to run.
- **Screen** (bottom): what the program prints, and a line where you type input.
- **Source** (right): your program, with the next line selected.

## 4. Step through the program

Press **F8** (Single step) to run one instruction. After each step:

- registers that changed are marked with `*` and a color;
- the Source and Disassembly panels move to the next instruction.

When the program calls `ReadInt`, it waits. Type a number in the Screen window
and press Enter.

Made a step too many? Press **Shift+F8** (Step back). Step back undoes single
steps only, up to the last 10,000. Run clears this history.

## 5. Run and stop

- **F9** (Run) runs until the program ends, an error happens, or a breakpoint is
  reached.
- **Esc** (Stop) stops a running program, for example an endless loop.
- The **Step delay** slider runs one instruction at a time with a pause, so you
  can watch the program work. At 0 ms, Run goes at full speed.
- Run stops after 100 million instructions, so an endless loop cannot hang the
  program. Change this limit in the editor's Options.

## 6. Breakpoints

Click the gutter to the left of a line number to set a breakpoint (a red dot),
or press Ctrl+B. Run stops before that line. Set breakpoints in the editor
before you press Emulate, or in the emulator's Source panel. In the Disassembly
panel, double-click an instruction.

## 7. More windows

The buttons below the main panels open more windows:

| Button | Shows |
|---|---|
| Vars | every variable with its value in decimal and hex |
| Stack | the stack around ESP, with ESP and EBP marked |
| Flags | CF, ZF, SF, OF and the other flags as 0 or 1 |
| Debug | breakpoints, and watches such as `eax + 1` or `[esi]` |
| Aux | the last 100 single steps and the instruction counter |
| CPU | a simple model of the CPU: Control Unit, ALU and registers |

## Keyboard

| Key | Action |
|---|---|
| F5 | Compile (editor) |
| Ctrl+F5 | Emulate (editor) |
| F8 | Single step |
| F10 | Step over a call |
| Shift+F8 | Step back |
| F9 | Run |
| Esc | Stop |
| Ctrl+G | Go to a memory address |
| Ctrl+B | Toggle breakpoint |
| Ctrl+Shift+P | Projector mode (large text, high contrast) |
| Ctrl+plus / Ctrl+minus | Larger or smaller text |

## Next

- Open the examples (File > Examples) and step through them.
- The **Syntax reference** lists everything the assembler accepts.
- The **Instruction reference** explains each instruction and the flags it changes.
