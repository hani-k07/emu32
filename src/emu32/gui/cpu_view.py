"""CPU structure window: a simplified basic-computer model animated from step records.

PC, AR, DR, IR and AC are mapped onto x86 as in section 8.7. The phases are replayed from
the trace record of the last single step; nothing here measures real hardware timing.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from emu32.gui import theme

NOTE = (
    "Simplified teaching model. A real x86 CPU has more registers and works differently "
    "inside. x86 also has more general registers (EAX, EBX, ECX, EDX, ESI, EDI, EBP, ESP) "
    "than the five shown here."
)
CAPTION = (
    "The Control Unit fetches and decodes instructions. The ALU performs addition, "
    "subtraction and logic operations. Registers are very fast temporary storage inside "
    "the CPU."
)
PHASES = ("Fetch", "Decode", "Execute", "Memory access")
REGISTERS = ("PC", "AR", "DR", "IR", "AC")


@dataclass(frozen=True)
class PhaseView:
    """What the diagram shows in one phase."""

    name: str
    values: dict[str, str]
    alu: str
    active: frozenset[str]  # boxes and registers to emphasize


def phases_for(record) -> list[PhaseView]:
    """The phases of one step, built from its trace record."""
    if record is None:
        return []
    hexed = record.data.hex(" ").upper()
    before, after = record.before, record.after
    pc_next = record.address + len(record.data)
    alu = "idle"
    if record.alu is not None:
        inputs = ", ".join(f"{v:X}" for v in record.alu.inputs)
        result = "flags only" if record.alu.result is None else f"{record.alu.result:X}"
        alu = f"{record.alu.operation} {inputs} -> {result}"
    fetch = {
        "PC": f"{record.address:08X}",
        "AR": f"{record.address:08X}",
        "DR": "",
        "IR": hexed,
        "AC": f"{before['EAX']:08X}",
    }
    views = [
        PhaseView("Fetch", fetch, "idle", frozenset({"control", "PC", "AR", "IR"})),
        PhaseView(
            "Decode",
            {**fetch, "PC": f"{pc_next:08X}", "IR": f"{hexed}  {record.text}"},
            "idle",
            frozenset({"control", "IR"}),
        ),
    ]
    decoded = views[-1].values
    executed = {**decoded, "PC": f"{after['EIP']:08X}", "AC": f"{after['EAX']:08X}"}
    views.append(
        PhaseView(
            "Execute",
            executed,
            alu,
            frozenset({"alu", "AC"} if record.alu else {"control", "AC"}),
        )
    )
    if record.accesses:
        last = record.accesses[-1]
        kinds = ", ".join(f"{a.kind} {a.address:08X}" for a in record.accesses)
        views.append(
            PhaseView(
                "Memory access",
                {**executed, "AR": f"{last.address:08X}", "DR": f"{last.value:0{2 * last.size}X}"},
                alu,
                frozenset({"AR", "DR"}),
            )
        )
        views[-1].values["DR"] += f"  ({kinds})"
    return views


class Diagram(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.view: PhaseView | None = None
        self.setMinimumSize(560, 330)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def show_view(self, view: PhaseView | None) -> None:
        self.view = view
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        palette = self.palette()
        text = palette.text().color()
        accent = theme.color("accent")
        fill = palette.base().color()
        active = self.view.active if self.view else frozenset()
        values = self.view.values if self.view else dict.fromkeys(REGISTERS, "")
        w, h = self.width(), self.height()
        mono = QFont("monospace")
        mono.setStyleHint(QFont.Monospace)

        def box(rect: QRectF, title: str, key: str) -> None:
            pen = QPen(accent if key in active else text, 3 if key in active else 1.5)
            p.setPen(pen)
            p.setBrush(fill)
            p.drawRoundedRect(rect, 8, 8)
            p.setPen(text)
            p.drawText(rect.adjusted(8, 6, -8, -6), Qt.AlignTop | Qt.AlignHCenter, title)

        outer = QRectF(10, 24, w - 20, h - 70)
        p.setPen(QPen(text, 2))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(outer, 12, 12)
        p.drawText(QRectF(outer.left() + 12, outer.top() - 20, 100, 18), Qt.AlignLeft, "CPU")

        left_w = outer.width() * 0.38
        control = QRectF(outer.left() + 20, outer.top() + 20, left_w, outer.height() * 0.32)
        alu = QRectF(outer.left() + 20, outer.bottom() - 20 - outer.height() * 0.4, left_w,
                     outer.height() * 0.4)  # fmt: skip
        regs = QRectF(control.right() + outer.width() * 0.12, outer.top() + 20,
                      outer.right() - 20 - control.right() - outer.width() * 0.12,
                      outer.height() - 40)  # fmt: skip
        box(control, "Control Unit", "control")
        box(alu, "ALU", "alu")
        box(regs, "Registers", "registers")
        p.setFont(mono)
        p.drawText(alu.adjusted(8, 28, -8, -6), Qt.AlignHCenter | Qt.TextWordWrap,
                   self.view.alu if self.view else "idle")  # fmt: skip

        row_h = (regs.height() - 36) / len(REGISTERS)
        for i, name in enumerate(REGISTERS):
            row = QRectF(
                regs.left() + 10, regs.top() + 30 + i * row_h, regs.width() - 20, row_h - 6
            )
            on = name in active
            p.setPen(QPen(accent if on else text, 2.5 if on else 1))
            p.setBrush(fill)
            p.drawRect(row)
            p.setPen(text)
            marker = "> " if on else "  "
            p.drawText(row.adjusted(6, 0, -6, 0), Qt.AlignVCenter | Qt.AlignLeft,
                       f"{marker}{name}  {values.get(name, '')}")  # fmt: skip

        # Control signals: dashed. Operands and results: solid, both ways.
        dashed = QPen(text, 1.5, Qt.DashLine)
        self._arrow(p, dashed, QPointF(control.center().x(), control.bottom()),
                    QPointF(alu.center().x(), alu.top()), both=False)  # fmt: skip
        self._arrow(p, dashed, QPointF(control.right(), control.center().y()),
                    QPointF(regs.left(), control.center().y()), both=False)  # fmt: skip
        self._arrow(p, QPen(text, 2.5), QPointF(alu.right(), alu.center().y()),
                    QPointF(regs.left(), alu.center().y()), both=True)  # fmt: skip

        legend_y = outer.bottom() + 12
        p.setFont(QFont())
        p.setPen(dashed)
        p.drawLine(QPointF(20, legend_y + 8), QPointF(60, legend_y + 8))
        p.setPen(text)
        p.drawText(QPointF(68, legend_y + 12), "control signal")
        p.setPen(QPen(text, 2.5))
        p.drawLine(QPointF(200, legend_y + 8), QPointF(240, legend_y + 8))
        p.setPen(text)
        p.drawText(QPointF(248, legend_y + 12), "operands and results")
        p.end()

    @staticmethod
    def _arrow(p: QPainter, pen: QPen, start: QPointF, end: QPointF, both: bool) -> None:
        p.setPen(pen)
        p.drawLine(start, end)
        p.setPen(QPen(pen.color(), 1))
        p.setBrush(pen.color())
        for tip, tail in ((end, start), (start, end)) if both else ((end, start),):
            direction = tip - tail
            length = max((direction.x() ** 2 + direction.y() ** 2) ** 0.5, 1)
            ux, uy = direction.x() / length, direction.y() / length
            p.drawPolygon(QPolygonF([
                tip,
                QPointF(tip.x() - 10 * ux + 5 * uy, tip.y() - 10 * uy - 5 * ux),
                QPointF(tip.x() - 10 * ux - 5 * uy, tip.y() - 10 * uy + 5 * ux),
            ]))  # fmt: skip


class CpuStructureWindow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("CPU structure")
        self.diagram = Diagram()
        self.phase_labels = [QLabel(name) for name in PHASES]
        self.phase_button = QPushButton("&Phase step")
        self.phase_mode = QCheckBox("Walk through the &phases of each instruction")
        self.phase_button.clicked.connect(self.next_phase)
        self.phase_mode.toggled.connect(lambda _on: self.show_record(self.record))
        phases = QHBoxLayout()
        phases.addWidget(QLabel("Phase:"))
        for label in self.phase_labels:
            phases.addWidget(label)
        phases.addStretch()
        phases.addWidget(self.phase_button)
        caption = QLabel(CAPTION)
        caption.setWordWrap(True)
        note = QLabel(NOTE)
        note.setWordWrap(True)
        note.setStyleSheet("font-style: italic")
        layout = QVBoxLayout(self)
        layout.addLayout(phases)
        layout.addWidget(self.phase_mode)
        layout.addWidget(self.diagram, 1)
        layout.addWidget(caption)
        layout.addWidget(note)
        self.record = None
        self.views: list[PhaseView] = []
        self.index = 0
        self.show_record(None)

    def show_record(self, record) -> None:
        """Show a new step: the first phase in phase mode, otherwise the end state."""
        self.record = record
        self.views = phases_for(record)
        self.index = 0 if self.phase_mode.isChecked() else max(len(self.views) - 1, 0)
        self._show()

    def next_phase(self) -> None:
        if self.index < len(self.views) - 1:
            self.index += 1
            self._show()

    def _show(self) -> None:
        view = self.views[self.index] if self.views else None
        self.diagram.show_view(view)
        present = {v.name for v in self.views}
        for label in self.phase_labels:
            name = label.text().lstrip("> ")
            current = view is not None and name == view.name
            label.setText(("> " if current else "") + name)
            label.setEnabled(name in present or not self.views)
            font = label.font()
            font.setBold(current)
            label.setFont(font)
        self.phase_button.setEnabled(self.index < len(self.views) - 1)
