"""One Qt stylesheet template, filled from the tokens of the active palette.

The stylesheet sets shapes, borders, spacing and interaction states. It sets no font sizes,
so widget fonts and zoom stay under program control.
"""

from __future__ import annotations

from emu32.gui.theme.tokens import RADIUS, SPACING

S1, S2, S3, S4 = SPACING[:4]  # 4, 8, 12, 16 px

TEMPLATE = """
QMainWindow, QDialog {{ background: {bg_panel}; }}

QToolBar {{
    background: {bg_raised}; border: none; border-bottom: 1px solid {border};
    padding: {s1}px; spacing: {s1}px;
}}
QToolBar::separator {{ background: {border}; width: 1px; margin: {s1}px {s2}px; }}
QToolButton {{
    background: transparent; border: 1px solid transparent; border-radius: {radius}px;
    padding: {s1}px {s2}px;
}}
QToolButton:hover {{ background: {bg_panel}; border-color: {border}; }}
QToolButton:pressed, QToolButton:checked {{ background: {selection}; }}
QToolButton:focus {{ border: 1px solid {accent}; }}
QToolButton:disabled {{ color: {text_muted}; }}

QPushButton {{
    background: {bg_raised}; border: 1px solid {border_control}; border-radius: {radius}px;
    padding: {s1}px {s3}px; min-height: {s4}px;
}}
QPushButton:hover {{ border-color: {accent}; }}
QPushButton:pressed {{ background: {selection}; }}
QPushButton:focus {{ border: 2px solid {accent}; }}
QPushButton:disabled {{ color: {text_muted}; background: {bg_panel}; border-color: {border}; }}
QPushButton[primary="true"] {{
    background: {accent}; color: {text_on_accent}; border-color: {accent};
}}
QPushButton[primary="true"]:focus {{ border: 2px solid {text_primary}; }}
QPushButton[primary="true"]:disabled {{
    background: {bg_panel}; color: {text_muted}; border-color: {border};
}}

QLineEdit, QSpinBox, QComboBox {{
    background: {bg_base}; border: 1px solid {border_control}; border-radius: {radius}px;
    padding: {s1}px {s2}px; selection-background-color: {selection};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border: 2px solid {accent}; }}
QLineEdit:disabled, QSpinBox:disabled, QComboBox:disabled {{ color: {text_muted}; }}
QComboBox QAbstractItemView {{
    background: {bg_raised}; border: 1px solid {border}; selection-background-color: {selection};
}}

QPlainTextEdit, QTextEdit, QTextBrowser {{
    background: {bg_base}; border: none; selection-background-color: {selection};
    selection-color: {text_primary};
}}

QMenuBar {{ background: {bg_raised}; border-bottom: 1px solid {border}; }}
QMenuBar::item {{ padding: {s1}px {s2}px; background: transparent; }}
QMenuBar::item:selected {{ background: {selection}; border-radius: {radius}px; }}
QMenuBar::item:disabled {{ color: {text_muted}; }}
QMenu {{ background: {bg_raised}; border: 1px solid {border}; padding: {s1}px; }}
QMenu::item {{ padding: {s1}px {s4}px {s1}px {s3}px; border-radius: {radius}px; }}
QMenu::item:selected {{ background: {selection}; }}
QMenu::item:disabled {{ color: {text_muted}; }}
QMenu::separator {{ height: 1px; background: {border}; margin: {s1}px {s2}px; }}

QTabWidget::pane {{ border: none; border-top: 1px solid {border}; }}
QTabBar::tab {{
    background: {bg_panel}; color: {text_muted}; padding: {s1}px {s3}px;
    border: 1px solid transparent; border-bottom: none;
}}
QTabBar::tab:selected {{
    background: {bg_base}; color: {text_primary}; border-color: {border};
    border-top: 2px solid {accent};
}}
QTabBar::tab:hover {{ color: {text_primary}; }}

QTableView, QTableWidget, QListView, QListWidget, QTreeView {{
    background: {bg_base}; alternate-background-color: {bg_panel}; gridline-color: {border};
    border: 1px solid {border}; selection-background-color: {selection};
    selection-color: {text_primary};
}}
QHeaderView::section {{
    background: {bg_raised}; color: {text_muted}; border: none;
    border-right: 1px solid {border}; border-bottom: 1px solid {border};
    padding: {s1}px {s2}px;
}}
QTableCornerButton::section {{ background: {bg_raised}; border: none; }}

QDockWidget {{ titlebar-close-icon: none; }}
QDockWidget::title {{
    background: {bg_raised}; padding: {s1}px {s2}px; border-bottom: 1px solid {border};
}}

QStatusBar {{ background: {bg_raised}; color: {text_muted}; border-top: 1px solid {border}; }}
QStatusBar QLabel {{ color: {text_muted}; padding: 0 {s2}px; }}

QSplitter::handle {{ background: {border}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

QScrollBar:vertical {{ background: {bg_panel}; width: {s3}px; margin: 0; }}
QScrollBar:horizontal {{ background: {bg_panel}; height: {s3}px; margin: 0; }}
QScrollBar::handle {{ background: {border_control}; border-radius: {radius}px; margin: 2px; }}
QScrollBar::handle:hover {{ background: {text_muted}; }}
QScrollBar::handle:vertical {{ min-height: {s4}px; }}
QScrollBar::handle:horizontal {{ min-width: {s4}px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QSlider::groove:horizontal {{ height: {s1}px; background: {border}; }}
QSlider::handle:horizontal {{
    background: {accent}; width: {s3}px; margin: -{s1}px 0; border-radius: {radius}px;
}}

QCheckBox, QRadioButton {{ spacing: {s2}px; }}
QToolTip {{
    background: {bg_raised}; color: {text_primary}; border: 1px solid {border};
    padding: {s1}px;
}}
QLabel:disabled {{ color: {text_muted}; }}
"""


def build(palette: dict[str, str]) -> str:
    """The stylesheet for one palette."""
    values = {name.replace(".", "_").replace("-", "_"): value for name, value in palette.items()}
    return TEMPLATE.format(radius=RADIUS, s1=S1, s2=S2, s3=S3, s4=S4, **values)
