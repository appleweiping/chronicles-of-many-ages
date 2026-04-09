from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LegendWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Legend"))
        layout.addWidget(QLabel(". plains"))
        layout.addWidget(QLabel("F forest"))
        layout.addWidget(QLabel("H hill"))
        layout.addWidget(QLabel("M mountain"))
        layout.addWidget(QLabel("~ water"))
        layout.addWidget(QLabel("S settlement"))
