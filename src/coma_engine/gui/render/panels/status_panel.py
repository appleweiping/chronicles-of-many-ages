from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from coma_engine.gui.types import WorldFrameProjection


class StatusPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.step_label = QLabel("Step: 0")
        self.phase_label = QLabel("Phase: Idle")
        self.selection_label = QLabel("Selection: none")
        layout.addWidget(self.step_label)
        layout.addWidget(self.phase_label)
        layout.addWidget(self.selection_label)

    def update_from_frame(self, frame: WorldFrameProjection, selected_ref: str | None) -> None:
        self.step_label.setText(f"Step: {frame.time_state.step}")
        self.phase_label.setText(f"Phase: {frame.time_state.current_phase_label}")
        self.selection_label.setText(f"Selection: {selected_ref or 'none'}")
