from __future__ import annotations

from PySide6.QtWidgets import QLabel, QHBoxLayout, QWidget

from coma_engine.gui.types import TimeStateProjection


class PhaseStrip(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QHBoxLayout(self)
        self.labels: list[QLabel] = []

    def set_time_state(self, time_state: TimeStateProjection) -> None:
        while self.labels:
            label = self.labels.pop()
            self.layout.removeWidget(label)
            label.deleteLater()
        for phase_name in time_state.phase_order:
            label = QLabel(phase_name)
            if phase_name in time_state.completed_phases:
                label.setStyleSheet("font-weight: bold; color: #d8e7ff;")
            self.layout.addWidget(label)
            self.labels.append(label)
