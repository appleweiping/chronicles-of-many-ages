from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class ControlPanel(QWidget):
    def __init__(self, on_step, on_pause, on_resume, on_step_batch):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.addWidget(QLabel("Time"))
        step_button = QPushButton("Advance 1")
        burst_button = QPushButton("Advance 5")
        pause_button = QPushButton("Pause")
        run_button = QPushButton("Auto Run")
        step_button.clicked.connect(on_step)
        burst_button.clicked.connect(on_step_batch)
        pause_button.clicked.connect(on_pause)
        run_button.clicked.connect(on_resume)
        layout.addWidget(step_button)
        layout.addWidget(burst_button)
        layout.addWidget(pause_button)
        layout.addWidget(run_button)
        layout.addStretch(1)
