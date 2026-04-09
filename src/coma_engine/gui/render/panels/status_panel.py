from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from coma_engine.gui.types import WorldFrameProjection, WorldStatusProjection


class StatusPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.headline_label = QLabel("World Summary")
        self.headline_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #f4f1de;")
        self.phase_label = QLabel("Phase: Idle")
        self.selection_label = QLabel("Selection: none")
        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.headline_label)
        layout.addWidget(self.phase_label)
        layout.addWidget(self.selection_label)
        layout.addWidget(self.summary_label)

    def update_from_frame(self, frame: WorldFrameProjection, selected_ref: str | None, status: WorldStatusProjection) -> None:
        self.headline_label.setText(status.headline)
        self.phase_label.setText(
            f"Phase trace: {frame.time_state.current_phase_label} · alerts {status.attention_count} · options {status.opportunity_count}"
        )
        self.selection_label.setText(f"Focus: {selected_ref or 'none'}")
        self.summary_label.setText("  |  ".join(status.summary_lines))
