from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LegendWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Legend"))
        layout.addWidget(QLabel("Warm halos: unrest, conflict, or major change"))
        layout.addWidget(QLabel("Bright rings: power centers and organized control"))
        layout.addWidget(QLabel("Blue waves: rumor or info flow activity"))
        layout.addWidget(QLabel("Soft fog: only partial player knowledge"))
        layout.addWidget(QLabel("White frame: current selection"))
