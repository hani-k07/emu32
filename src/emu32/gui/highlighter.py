from __future__ import annotations

import re

from PySide6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument

from emu32.gui import theme
from emu32.session import syntax_words

_TOKEN = re.compile(
    r"(?P<comment>;.*)"
    r"|(?P<string>'[^']*'?|\"[^\"]*\"?)"
    r"|(?P<directive>\.[a-z0-9?]+)"
    r"|(?P<number>\b(?:0x[0-9a-f]+|[0-9][0-9a-f]*h|[01]+b|[0-9]+d?)\b)"
    r"|(?P<word>[a-z_@?$][\w@?$]*)",
    re.IGNORECASE,
)


class AsmHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self.words = syntax_words()
        self.refresh_colors()

    def refresh_colors(self) -> None:
        self.formats = {}
        for name, token, bold in (
            ("instructions", "syn.instruction", True),
            ("registers", "syn.register", False),
            ("number", "syn.number", False),
            ("string", "syn.string", False),
            ("comment", "syn.comment", False),
            ("directive", "syn.directive", True),
            ("routines", "syn.label", False),
        ):
            fmt = QTextCharFormat()
            fmt.setForeground(theme.color(token))
            if bold:
                fmt.setFontWeight(QFont.Bold)
            if name == "comment":
                fmt.setFontItalic(True)
            self.formats[name] = fmt
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt override
        for match in _TOKEN.finditer(text):
            kind = match.lastgroup
            start, length = match.start(), match.end() - match.start()
            if kind == "word":
                word = match.group(0).lower()
                kind = next(
                    (
                        k
                        for k in ("instructions", "registers", "directives", "routines")
                        if word in self.words[k]
                    ),
                    None,
                )
                if kind == "directives":
                    kind = "directive"
            if kind:
                self.setFormat(start, length, self.formats[kind])
