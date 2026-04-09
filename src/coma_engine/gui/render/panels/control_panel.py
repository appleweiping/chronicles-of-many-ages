from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class ControlPanel(QWidget):
    def __init__(self, on_step, on_pause, on_resume):
        super().__init__()
        layout = QHBoxLayout(self)
        step_button = QPushButton("Step")
        pause_button = QPushButton("Pause")
        run_button = QPushButton("Run")
        step_button.clicked.connect(on_step)
        pause_button.clicked.connect(on_pause)
        run_button.clicked.connect(on_resume)
        layout.addWidget(step_button)
        layout.addWidget(pause_button)
        layout.addWidget(run_button)
