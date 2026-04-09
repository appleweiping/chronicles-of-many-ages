from __future__ import annotations

from PySide6.QtWidgets import QLabel, QListWidget, QVBoxLayout, QWidget


class TimelinePanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Timeline"))
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

    def set_lines(self, lines: list[str]) -> None:
        self.list_widget.clear()
        self.list_widget.addItems(lines)
