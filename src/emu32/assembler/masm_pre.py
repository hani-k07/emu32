"""MASM features expanded into plain lines before the assembler's first pass.

Handled here: TEXTEQU (and EQU <text>), macros with parameters, defaults and LOCAL labels
(plus the course library's mWrite family, built in), STRUCT definitions (collected for the
assembler, which lays them out), the decision directives .IF/.ELSEIF/.ELSE/.ENDIF,
.WHILE/.ENDW, .REPEAT/.UNTIL/.UNTILCXZ, .BREAK and .CONTINUE, and anonymous @@ labels.

Lines arrive cleaned (lowercase outside strings, numbers as 0x hex). Every generated line
keeps the number of the source line it came from, so errors and the listing point there.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from emu32.assembler.cleaner import SourceLine, clean, map_unquoted
from emu32.assembler.errors import AsmError, AsmMessage
from emu32.assembler.operands import NAME, Scope, evaluate

MAX_DEPTH = 32  # nested macro calls; deeper is almost certainly endless recursion

# The course library's text macros (Macros.inc), written from their documented behavior.
BUILT_IN_MACROS = """
mwrite macro text
    local string
    .data
    string byte text, 0
    .code
    push edx
    mov edx, offset string
    call writestring
    pop edx
endm
mwriteln macro text
    mwrite text
    call crlf
endm
mwritestring macro buffer
    push edx
    mov edx, offset buffer
    call writestring
    pop edx
endm
mwritespace macro count:=<1>
    local spaces
    .data
    spaces byte count dup(' '), 0
    .code
    push edx
    mov edx, offset spaces
    call writestring
    pop edx
endm
mreadstring macro buffer
    push ecx
    push edx
    mov edx, offset buffer
    mov ecx, sizeof buffer
    call readstring
    pop edx
    pop ecx
endm
mgotoxy macro x, y
    push edx
    mov dh, y
    mov dl, x
    call gotoxy
    pop edx
endm
mdumpmem macro address, itemcount, componentsize
    push ebx
    push ecx
    push esi
    mov esi, address
    mov ecx, itemcount
    mov ebx, componentsize
    call dumpmem
    pop esi
    pop ecx
    pop ebx
endm
"""

_HIGH_LEVEL = (".if", ".elseif", ".else", ".endif", ".while", ".endw", ".repeat", ".until",
               ".untilcxz", ".break", ".continue")  # fmt: skip
_UNSIGNED_JUMP = {"==": "je", "!=": "jne", ">": "ja", ">=": "jae", "<": "jb", "<=": "jbe"}
_SIGNED_JUMP = {"==": "je", "!=": "jne", ">": "jg", ">=": "jge", "<": "jl", "<=": "jle"}
_OPPOSITE = {"==": "!=", "!=": "==", ">": "<=", "<=": ">", "<": ">=", ">=": "<"}
_MIRROR = {"==": "==", "!=": "!=", ">": "<", "<": ">", ">=": "<=", "<=": ">="}
_FLAGS = {"carry?": "c", "zero?": "z", "sign?": "s", "overflow?": "o", "parity?": "p"}
_SIGNED_DECL = re.compile(
    rf"(?:^|\s)({NAME})\s*:?\s+(?:sbyte|sword|sdword)\b|({NAME})\s*:\s*s(?:byte|word|dword)\b"
)
_CONSTANT_OPERAND = re.compile(r"-?0x[0-9a-f]+|'[^']*'|\"[^\"]*\"")
_WORD = re.compile(NAME)
_REGISTER_PTR = re.compile(
    r"^s?(?:byte|word|dword) ptr ((?:e?[abcd]x|[abcd][hl]|e?[sd]i|e?[bs]p))$"
)


class PreError(Exception):
    def __init__(self, text: str, line: int | None = None) -> None:
        super().__init__(text)
        self.line = line  # when the error belongs to another line than the current one


class _ExitMacro(Exception):
    """EXITM: stop expanding the current macro."""


_REPEATS = {"rept", "repeat", "for", "irp", "forc", "irpc", "while"}
_CONDITIONALS = {
    "if", "ife", "ifb", "ifnb", "ifidn", "ifidni", "ifdif", "ifdifi", "ifdef", "ifndef",
}  # fmt: skip
_CONDITION_WORDS = _CONDITIONALS | {"else" + w for w in _CONDITIONALS} | {"else", "endif"}
_CONSTANT_LINE = re.compile(rf"^({NAME})\s*(?:=|equ\b)\s*([^<].*)$")
MAX_REPEATS = 10_000


@dataclass
class Macro:
    params: list[tuple[str, str | None, bool]]  # name, default, required
    body: list[str] = field(default_factory=list)
    line: int = 0


@dataclass
class StructField:
    name: str
    directive: str
    initializer: str


def split_args(text: str) -> list[str]:
    """Split on top-level commas, keeping quotes, brackets and <text> groups together."""
    parts, depth, quote, current = [], 0, None, []
    for char in text:
        if quote:
            quote = None if char == quote else quote
        elif char in "'\"":
            quote = char
        elif char in "([<":
            depth += 1
        elif char in ")]>":
            depth -= 1
        elif char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    last = "".join(current).strip()
    if last or parts:
        parts.append(last)
    return parts


def _unbracket(text: str) -> str:
    text = text.strip()
    return text[1:-1].strip() if text.startswith("<") and text.endswith(">") else text


def _top_level_split(text: str, separator: str) -> list[str]:
    parts, depth, quote, start, i = [], 0, None, 0, 0
    while i < len(text):
        char = text[i]
        if quote:
            quote = None if char == quote else quote
        elif char in "'\"":
            quote = char
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif depth == 0 and text.startswith(separator, i):
            parts.append(text[start:i].strip())
            i += len(separator)
            start = i
            continue
        i += 1
    parts.append(text[start:].strip())
    return parts


def _wrapped(text: str) -> bool:
    """True when the whole text is one (...) group."""
    if not (text.startswith("(") and text.endswith(")")):
        return False
    depth = 0
    for index, char in enumerate(text):
        depth += char == "("
        depth -= char == ")"
        if depth == 0 and index < len(text) - 1:
            return False
    return True


class _Pre:
    def __init__(self, lines: list[SourceLine], errors: list[AsmMessage]) -> None:
        self.errors = errors
        self.out: list[SourceLine] = []
        self.macros: dict[str, Macro] = {}
        self.texts: dict[str, str] = {}
        self.structs: dict[str, list[StructField]] = {}
        self.signed: set[str] = set()
        for line in lines:
            for match in _SIGNED_DECL.finditer(line.text):
                self.signed.add(match.group(1) or match.group(2))
        self.counter = 0
        self.blocks: list[dict] = []
        self.defining: tuple[str, Macro] | None = None
        self.nesting = 0  # REPT/FOR/WHILE blocks open inside a macro or block being read
        self.capture: dict | None = None  # a REPT/FOR/FORC/WHILE block being read
        self.conditions: list[dict] = []  # open IF blocks
        self.consts: dict[str, int] = {}  # numeric constants seen so far, for IF and REPT
        self.struct: tuple[str, int, list[StructField]] | None = None
        for line in clean(BUILT_IN_MACROS)[0]:
            self._line(0, line.text, 0)

    def label(self, kind: str) -> str:
        self.counter += 1
        return f"__{kind}{self.counter}"

    def emit(self, number: int, text: str) -> None:
        self.out.append(SourceLine(number, text))

    def run(self, lines: list[SourceLine]) -> list[SourceLine]:
        for line in lines:
            try:
                self._line(line.number, line.text, 0)
            except PreError as error:
                self.errors.append(AsmMessage(error.line or line.number, str(error)))
        if self.defining:
            name, macro = self.defining
            self.errors.append(AsmMessage(macro.line, f"macro '{name}' has no ENDM"))
        if self.struct:
            self.errors.append(AsmMessage(self.struct[1], f"STRUCT '{self.struct[0]}' has no ENDS"))
        if self.capture:
            self.errors.append(
                AsmMessage(self.capture["line"], f"{self.capture['kind'].upper()} has no ENDM")
            )
        for condition in self.conditions:
            self.errors.append(AsmMessage(condition["line"], "IF has no ENDIF"))
        for block in self.blocks:
            closing = {"if": ".ENDIF", "while": ".ENDW", "repeat": ".UNTIL"}[block["kind"]]
            self.errors.append(AsmMessage(block["line"], f"this block has no {closing}"))
        return self.out

    # One line

    def _line(self, number: int, text: str, depth: int) -> None:
        words = text.split(" ")
        if self.defining is not None:
            name, macro = self.defining
            if self._block_ends(words):
                self.macros[name] = macro
                self.defining = None
            elif len(words) > 1 and words[1] == "macro":
                raise PreError("a macro cannot be defined inside another macro")
            else:
                macro.body.append(text)
            return
        if self.capture is not None:
            if self._block_ends(words):
                block, self.capture = self.capture, None
                try:
                    self._repeat(block)
                except PreError as error:
                    error.line = error.line or block["line"]  # point at REPT/FOR/WHILE
                    raise
            else:
                self.capture["body"].append(text)
            return
        if self.struct is not None:
            self._struct_line(text, words)
            return
        if words[0] in _CONDITION_WORDS:
            self._conditional(number, words[0], text[len(words[0]) :].strip())
            return
        if not all(c["active"] for c in self.conditions):
            return
        text = self._substitute_texts(text)
        words = text.split(" ")
        second = words[1] if len(words) > 1 else ""
        rest = text[len(words[0]) :].strip()
        if words[0] == "exitm":
            raise _ExitMacro
        if words[0] in _REPEATS:
            self.capture = {"kind": words[0], "args": rest, "body": [], "line": number,
                            "depth": depth}  # fmt: skip
            return
        constant = _CONSTANT_LINE.match(text)
        if constant:
            try:
                self.consts[constant.group(1)] = self._value(constant.group(2))
            except PreError:
                pass  # uses a variable address; the assembler works it out
        if second == "macro":
            self._define_macro(number, words[0], text.split(" ", 2)[2] if len(words) > 2 else "")
            return
        if second in ("struct", "struc"):
            self.struct = (words[0], number, [])
            return
        if second == "textequ" or (second == "equ" and rest[3:].strip().startswith("<")):
            self.texts[words[0]] = _unbracket(text.split(" ", 2)[2] if len(words) > 2 else "")
            return
        if words[0] in _HIGH_LEVEL:
            self._high_level(number, words[0], rest)
            return
        label = re.match(rf"^({NAME}\s*::?)\s*(.*)$", text)
        if label and label.group(2).split(" ")[0] in self.macros:
            self.emit(number, label.group(1))
            text = label.group(2)
            words = text.split(" ")
        if words[0] in self.macros:
            self._expand(number, words[0], text[len(words[0]) :].strip(), depth)
            return
        self.emit(number, text)

    def _substitute_texts(self, text: str) -> str:
        if not self.texts:
            return text
        return map_unquoted(
            text,
            lambda part: _WORD.sub(lambda m: self.texts.get(m.group(0), m.group(0)), part),
        )

    # Macros

    def _define_macro(self, number: int, name: str, params_text: str) -> None:
        params = []
        for part in split_args(params_text):
            pname, _, option = (piece.strip() for piece in part.partition(":"))
            if option.startswith("="):
                params.append((pname, _unbracket(option[1:]), False))
            else:
                params.append((pname, None, option == "req"))
        self.defining = (name, Macro(params, line=number))

    def _expand(self, number: int, name: str, args_text: str, depth: int) -> None:
        if depth >= MAX_DEPTH:
            raise PreError(f"macro '{name}' calls itself too deeply")
        macro = self.macros[name]
        args = [_unbracket(a) for a in split_args(args_text)]
        if len(args) > len(macro.params):
            raise PreError(f"macro '{name}' takes {len(macro.params)} arguments, not {len(args)}")
        values: dict[str, str] = {}
        for index, (pname, default, required) in enumerate(macro.params):
            value = args[index] if index < len(args) and args[index] != "" else default
            if value is None:
                if required:
                    raise PreError(f"macro '{name}' needs a value for '{pname}'")
                value = ""
            values[pname] = value
        body = list(macro.body)
        while body and body[0].startswith("local "):
            for local in split_args(body.pop(0)[6:]):
                values[local] = self.label(f"m_{local}_")
        open_conditions = len(self.conditions)
        try:
            for line in body:
                self._line(number, _fill(line, values), depth + 1)
        except _ExitMacro:
            del self.conditions[open_conditions:]

    # Conditional assembly and repeat blocks

    def _block_ends(self, words: list[str]) -> bool:
        """Track REPT/FOR/WHILE nesting inside a block being read; True at its own ENDM."""
        if words[0] in _REPEATS:
            self.nesting += 1
        elif words[0] == "endm":
            if self.nesting == 0:
                return True
            self.nesting -= 1
        return False

    def _value(self, expression: str) -> int:
        try:
            return evaluate(expression, Scope(constants=self.consts), 0)
        except AsmError as error:
            raise PreError(f"this needs a constant expression: {error.text}") from None

    def _conditional(self, number: int, word: str, rest: str) -> None:
        outer = all(c["active"] for c in self.conditions)
        if word in _CONDITIONALS:
            value = outer and self._test(word, rest)
            self.conditions.append({"active": value, "taken": value, "outer": outer,
                                    "line": number})  # fmt: skip
            return
        if not self.conditions:
            raise PreError(f"{word.upper()} without a matching IF")
        top = self.conditions[-1]
        if word == "endif":
            self.conditions.pop()
        elif word == "else":
            top["active"] = top["outer"] and not top["taken"]
            top["taken"] = True
        else:  # ELSEIF, ELSEIFB, ...
            value = top["outer"] and not top["taken"] and self._test(word[4:], rest)
            top["active"] = value
            top["taken"] = top["taken"] or value

    def _test(self, word: str, rest: str) -> bool:
        if word in ("if", "ife"):
            return (self._value(rest) != 0) == (word == "if")
        if word in ("ifb", "ifnb"):
            return (_unbracket(rest) == "") == (word == "ifb")
        if word in ("ifdef", "ifndef"):
            known = rest in self.consts or rest in self.texts or rest in self.macros
            return (known or rest in self.structs) == (word == "ifdef")
        parts = split_args(rest)
        if len(parts) != 2:
            raise PreError(f"{word.upper()} compares two texts: {word.upper()} <a>, <b>")
        same = _unbracket(parts[0]) == _unbracket(parts[1])
        return same == word.startswith("ifidn")

    def _repeat(self, block: dict) -> None:
        kind, args, body = block["kind"], block["args"], block["body"]
        number, depth = block["line"], block["depth"]

        def replay(values: dict[str, str]) -> None:
            for line in body:
                self._line(number, _fill(line, values) if values else line, depth + 1)

        if kind in ("rept", "repeat"):
            for _ in range(self._value(args)):
                replay({})
        elif kind in ("for", "irp", "forc", "irpc"):
            name, _, items = (part.strip() for part in args.partition(","))
            if not name or not items:
                raise PreError(f"write {kind.upper()} name, <items>")
            if kind in ("for", "irp"):
                values = [_unbracket(item) for item in split_args(_unbracket(items))]
            else:
                values = list(_unbracket(items))
            for value in values:
                replay({name: value})
        else:  # WHILE expression ... ENDM
            for _ in range(MAX_REPEATS):
                if not self._value(args):
                    return
                replay({})
            raise PreError(f"WHILE repeated {MAX_REPEATS} times; is its condition ever false?")

    # Structures

    def _struct_line(self, text: str, words: list[str]) -> None:
        name, number, fields = self.struct
        if words[0] == name and len(words) > 1 and words[1] == "ends":
            self.structs[name] = fields
            self.struct = None
            return
        if len(words) < 3:
            raise PreError(f"cannot read the field '{text}'; write: name TYPE value")
        fields.append(StructField(words[0], words[1], text.split(" ", 2)[2]))

    # Decision directives

    def _high_level(self, number: int, word: str, rest: str) -> None:
        if word == ".if":
            block = {
                "kind": "if",
                "line": number,
                "next": self.label("if"),
                "end": self.label("endif"),
            }
            self._jump_if_false(number, rest, block["next"])
            self.blocks.append(block)
        elif word in (".elseif", ".else", ".endif"):
            block = self._innermost(word, ("if",))
            if word == ".endif":
                self.blocks.pop()
                if block["next"]:
                    self.emit(number, f"{block['next']}:")
                self.emit(number, f"{block['end']}:")
                return
            if block["next"] is None:
                raise PreError(f"{word.upper()} cannot follow .ELSE")
            self.emit(number, f"jmp {block['end']}")
            self.emit(number, f"{block['next']}:")
            if word == ".elseif":
                block["next"] = self.label("if")
                self._jump_if_false(number, rest, block["next"])
            else:
                block["next"] = None
        elif word == ".while":
            block = {
                "kind": "while",
                "line": number,
                "top": self.label("while"),
                "test": self.label("test"),
                "end": self.label("endw"),
                "cond": rest,
            }
            self.emit(number, f"jmp {block['test']}")
            self.emit(number, f"{block['top']}:")
            self.blocks.append(block)
        elif word == ".endw":
            block = self._innermost(word, ("while",))
            self.blocks.pop()
            self.emit(number, f"{block['test']}:")
            self._jump_if_true(number, block["cond"], block["top"])
            self.emit(number, f"{block['end']}:")
        elif word == ".repeat":
            block = {"kind": "repeat", "line": number, "top": self.label("repeat"),
                     "test": self.label("test"), "end": self.label("until")}  # fmt: skip
            self.emit(number, f"{block['top']}:")
            self.blocks.append(block)
        elif word in (".until", ".untilcxz"):
            block = self._innermost(word, ("repeat",))
            self.blocks.pop()
            self.emit(number, f"{block['test']}:")
            if word == ".until":
                self._jump_if_false(number, rest, block["top"])
            elif rest:
                raise PreError(".UNTILCXZ with a condition is not supported; use .UNTIL")
            else:
                self.emit(number, f"loop {block['top']}")
            self.emit(number, f"{block['end']}:")
        else:  # .break / .continue, optionally followed by .IF condition
            loop = next((b for b in reversed(self.blocks) if b["kind"] != "if"), None)
            if loop is None:
                raise PreError(f"{word.upper()} belongs inside .WHILE or .REPEAT")
            target = loop["end"] if word == ".break" else loop["test"]
            if rest.startswith(".if "):
                self._jump_if_true(number, rest[4:], target)
            elif rest:
                raise PreError(f"write {word.upper()} .IF condition")
            else:
                self.emit(number, f"jmp {target}")

    def _innermost(self, word: str, kinds: tuple[str, ...]) -> dict:
        if not self.blocks or self.blocks[-1]["kind"] not in kinds:
            opener = {"if": ".IF", "while": ".WHILE", "repeat": ".REPEAT"}[kinds[0]]
            raise PreError(f"{word.upper()} without a matching {opener}")
        return self.blocks[-1]

    def _jump_if_false(self, number: int, condition: str, target: str) -> None:
        self._condition(number, condition, target, when=False)

    def _jump_if_true(self, number: int, condition: str, target: str) -> None:
        self._condition(number, condition, target, when=True)

    def _condition(self, number: int, text: str, target: str, when: bool) -> None:
        """Jump to target when the condition's truth equals `when`, with short-circuit
        evaluation of || and && as MASM does."""
        text = text.strip()
        if not text:
            raise PreError("a condition is missing")
        alternatives = _top_level_split(text, "||")
        if len(alternatives) > 1:
            if when:
                for part in alternatives:
                    self._condition(number, part, target, True)
            else:
                skip = self.label("or")
                for part in alternatives[:-1]:
                    self._condition(number, part, skip, True)
                self._condition(number, alternatives[-1], target, False)
                self.emit(number, f"{skip}:")
            return
        required = _top_level_split(text, "&&")
        if len(required) > 1:
            if when:
                skip = self.label("and")
                for part in required[:-1]:
                    self._condition(number, part, skip, False)
                self._condition(number, required[-1], target, True)
                self.emit(number, f"{skip}:")
            else:
                for part in required:
                    self._condition(number, part, target, False)
            return
        if text.startswith("!") and not text.startswith("!="):
            self._condition(number, text[1:], target, not when)
            return
        if _wrapped(text):
            self._condition(number, text[1:-1], target, when)
            return
        self._compare(number, text, target, when)

    def _compare(self, number: int, text: str, target: str, when: bool) -> None:
        if text in _FLAGS:
            self.emit(number, f"j{'' if when else 'n'}{_FLAGS[text]} {target}")
            return
        match = re.search(r"==|!=|>=|<=|>|<", map_unquoted(text, lambda p: p))
        if match is None:
            left, op, right = text, "!=", "0x0"
        else:
            left, op, right = (
                text[: match.start()].strip(),
                match.group(0),
                text[match.end() :].strip(),
            )
        if not left or not right:
            raise PreError(f"cannot read the condition '{text}'")
        constant = _constant_truth(left, op, right)
        if constant is not None:  # `.WHILE 1` and similar: decided now, no compare
            if constant == when:
                self.emit(number, f"jmp {target}")
            return
        if _CONSTANT_OPERAND.fullmatch(left):
            left, right, op = right, left, _MIRROR[op]
        signed = any(name in self.signed for name in _WORD.findall(f"{left} {right}")) or bool(
            re.search(r"\bs(?:byte|word|dword) ptr\b", f"{left} {right}")
        )
        if not when:
            op = _OPPOSITE[op]
        # `SDWORD PTR ebx` only asks for a signed compare; a register needs no size.
        left, right = (_REGISTER_PTR.sub(r"\1", side) for side in (left, right))
        self.emit(number, f"cmp {left}, {right}")
        self.emit(number, f"{(_SIGNED_JUMP if signed else _UNSIGNED_JUMP)[op]} {target}")


def _constant_truth(left: str, op: str, right: str) -> bool | None:
    """The value of a condition between two numbers, or None if either is not a number."""
    numbers = [re.fullmatch(r"(-?)0x([0-9a-f]+)", side) for side in (left, right)]
    if not all(numbers):
        return None
    a, b = (int(m.group(2), 16) * (-1 if m.group(1) else 1) for m in numbers)
    return {"==": a == b, "!=": a != b, ">": a > b, ">=": a >= b, "<": a < b, "<=": a <= b}[op]


def _fill(line: str, values: dict[str, str]) -> str:
    """Put macro arguments into a body line: whole names outside quotes, and &name& inside."""

    def outside(part: str) -> str:
        part = _WORD.sub(lambda m: values.get(m.group(0), m.group(0)), part)
        return part.replace("&", "")

    def inside(quoted: str) -> str:
        return re.sub(rf"&({NAME})&?", lambda m: values.get(m.group(1), m.group(0)), quoted)

    out, last = [], 0
    for match in re.finditer(r"'[^']*'|\"[^\"]*\"", line):
        out.append(outside(line[last : match.start()]))
        out.append(inside(match.group(0)))
        last = match.end()
    out.append(outside(line[last:]))
    return "".join(out)


def _anonymous_labels(lines: list[SourceLine], errors: list[AsmMessage]) -> list[SourceLine]:
    """`@@:` labels: @B is the nearest one at or above, @F the nearest one below."""
    marks = [
        i for i, line in enumerate(lines) if line.text == "@@:" or line.text.startswith("@@: ")
    ]
    if not marks and not any("@f" in line.text or "@b" in line.text for line in lines):
        return lines
    names = {index: f"__anon{k}" for k, index in enumerate(marks)}
    out = []
    for index, line in enumerate(lines):
        text = line.text
        if index in names:
            text = names[index] + ":" + text[3:]
        before = [m for m in marks if m <= index]
        after = [m for m in marks if m > index]

        def replace(match: re.Match, before=before, after=after, number=line.number) -> str:
            pool = after[:1] if match.group(0) == "@f" else before[-1:]
            if not pool:
                errors.append(
                    AsmMessage(number, f"{match.group(0).upper()} has no @@: label to go to")
                )
                return match.group(0)
            return names[pool[0]]

        text = map_unquoted(
            text, lambda part: re.sub(r"(?<![\w@?$])@[fb](?![\w@?$])", replace, part)
        )
        out.append(SourceLine(line.number, text))
    return out


def preprocess(
    lines: list[SourceLine], errors: list[AsmMessage]
) -> tuple[list[SourceLine], dict[str, list[StructField]]]:
    pre = _Pre(lines, errors)
    out = pre.run(lines)
    return _anonymous_labels(out, errors), pre.structs
