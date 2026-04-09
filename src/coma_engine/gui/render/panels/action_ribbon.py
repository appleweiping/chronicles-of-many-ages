from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from coma_engine.gui.types import InterventionOptionProjection, MapMode


MAP_MODE_LABELS: tuple[tuple[MapMode, str], ...] = (
    ("world", "World"),
    ("control", "Control"),
    ("resources", "Resources"),
    ("pressure", "Pressure"),
    ("infoflow", "InfoFlow"),
)


class ActionRibbon(QWidget):
    def __init__(self, on_step, on_run, on_pause, on_step_batch, on_mode_change, on_select_action, on_commit_action, on_cycle_overlay=None, on_objective_review=None):
        super().__init__()
        self.setFixedHeight(138)
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(10)

        self.left_box = QFrame()
        self.left_box.setFrameShape(QFrame.Shape.StyledPanel)
        left = QVBoxLayout(self.left_box)
        left.addWidget(QLabel("Time And World"))
        row = QHBoxLayout()
        self.step_button = QPushButton("Step")
        self.run_button = QPushButton("Run")
        self.pause_button = QPushButton("Pause")
        self.batch_button = QPushButton("Step x5")
        self.step_button.clicked.connect(on_step)
        self.run_button.clicked.connect(on_run)
        self.pause_button.clicked.connect(on_pause)
        self.batch_button.clicked.connect(on_step_batch)
        for button in (self.step_button, self.run_button, self.pause_button, self.batch_button):
            row.addWidget(button)
        left.addLayout(row)

        utility_row = QHBoxLayout()
        self.overlay_button = QPushButton("Cycle Overlay")
        self.objective_button = QPushButton("Objective")
        if on_cycle_overlay is not None:
            self.overlay_button.clicked.connect(on_cycle_overlay)
        if on_objective_review is not None:
            self.objective_button.clicked.connect(on_objective_review)
        utility_row.addWidget(self.overlay_button)
        utility_row.addWidget(self.objective_button)
        left.addLayout(utility_row)

        self.mode_buttons: dict[str, QPushButton] = {}
        mode_row = QHBoxLayout()
        for mode, label in MAP_MODE_LABELS:
            button = QPushButton(label)
            button.clicked.connect(lambda _checked=False, selected=mode: on_mode_change(selected))
            mode_row.addWidget(button)
            self.mode_buttons[mode] = button
        left.addLayout(mode_row)
        root.addWidget(self.left_box, stretch=3)

        self.middle_box = QFrame()
        self.middle_box.setFrameShape(QFrame.Shape.StyledPanel)
        middle = QVBoxLayout(self.middle_box)
        middle.addWidget(QLabel("Context Actions"))
        self.context_row = QHBoxLayout()
        self._action_buttons: list[QPushButton] = []
        middle.addLayout(self.context_row)
        root.addWidget(self.middle_box, stretch=4)

        self.right_box = QFrame()
        self.right_box.setFrameShape(QFrame.Shape.StyledPanel)
        right = QVBoxLayout(self.right_box)
        self.preview_title = QLabel("Action Preview")
        self.preview_body = QLabel("Select an action to see non-authoritative guidance.")
        self.preview_body.setWordWrap(True)
        self.commit_button = QPushButton("Commit")
        self.commit_button.setEnabled(False)
        self.commit_button.clicked.connect(on_commit_action)
        right.addWidget(self.preview_title)
        right.addWidget(self.preview_body, stretch=1)
        right.addWidget(self.commit_button)
        self._on_select_action = on_select_action
        self._current_target_ref: str | None = None
        root.addWidget(self.right_box, stretch=3)

    def set_mode(self, map_mode: MapMode) -> None:
        for mode, button in self.mode_buttons.items():
            button.setEnabled(mode != map_mode)

    def set_options(self, options: tuple[InterventionOptionProjection, ...], selected_action_id: str | None, selected_target_ref: str | None) -> None:
        while self._action_buttons:
            button = self._action_buttons.pop()
            self.context_row.removeWidget(button)
            button.deleteLater()
        self._current_target_ref = selected_target_ref
        if not options:
            placeholder = QPushButton("No legal actions here")
            placeholder.setEnabled(False)
            self.context_row.addWidget(placeholder)
            self._action_buttons.append(placeholder)
            self.preview_title.setText("Action Preview")
            self.preview_body.setText("Select a tile, figure, or settlement with visible legal interventions.")
            self.commit_button.setEnabled(False)
            return
        selected_option: InterventionOptionProjection | None = None
        for option in options:
            button = QPushButton(option.label)
            button.setEnabled(option.enabled)
            button.clicked.connect(lambda _checked=False, action_id=option.action_id, target_ref=option.target_ref: self._on_select_action(action_id, target_ref))
            self.context_row.addWidget(button)
            self._action_buttons.append(button)
            if option.action_id == selected_action_id and option.target_ref == selected_target_ref:
                selected_option = option
        if selected_option is None:
            selected_option = next((option for option in options if option.enabled), options[0])
        self._render_preview(selected_option)

    def _render_preview(self, option: InterventionOptionProjection) -> None:
        self.preview_title.setText(option.label)
        lines = [option.description]
        if option.impact_hint:
            lines.append(option.impact_hint)
        lines.extend(option.preview_lines)
        self.preview_body.setText("\n".join(lines))
        self.commit_button.setEnabled(option.enabled)
