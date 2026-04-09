from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from coma_engine.gui.types import TopBarProjection


class TopBar(QWidget):
    def __init__(self, on_step, on_pause, on_run):
        super().__init__()
        self.setFixedHeight(58)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        self.scenario_label = QLabel("Scenario")
        self.step_label = QLabel("Step 0")
        self.time_label = QLabel("Idle")
        self.speed_label = QLabel("Paused")
        self.influence_label = QLabel("Influence 0")
        self.visibility_label = QLabel("Visibility Obscured")
        self.objective_label = QLabel("No active objective")
        self.objective_label.setMinimumWidth(220)
        self.atmosphere_label = QLabel("")
        self.atmosphere_label.setWordWrap(True)

        for widget in (
            self.scenario_label,
            self.step_label,
            self.time_label,
            self.speed_label,
            self.influence_label,
            self.visibility_label,
            self.objective_label,
        ):
            layout.addWidget(widget)

        layout.addWidget(self.atmosphere_label, stretch=1)

        self.pause_button = QPushButton("Pause")
        self.run_button = QPushButton("Run")
        self.step_button = QPushButton("Step")
        self.pause_button.clicked.connect(on_pause)
        self.run_button.clicked.connect(on_run)
        self.step_button.clicked.connect(on_step)
        layout.addWidget(self.pause_button)
        layout.addWidget(self.run_button)
        layout.addWidget(self.step_button)

    def render(self, projection: TopBarProjection) -> None:
        self.scenario_label.setText(projection.scenario_name)
        self.step_label.setText(projection.step_label)
        self.time_label.setText(projection.time_state_label)
        self.speed_label.setText(projection.speed_label)
        self.influence_label.setText(projection.influence_label)
        self.visibility_label.setText(projection.visibility_label)
        self.objective_label.setText(projection.objective_label)
        self.atmosphere_label.setText("  |  ".join(projection.atmosphere_labels))
