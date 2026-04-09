from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

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
        self.setFixedHeight(142)
        root = QHBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(10)

        self.left_box = QFrame()
        self.left_box.setFrameShape(QFrame.Shape.StyledPanel)
        self.left_box.setMaximumWidth(360)
        left = QVBoxLayout(self.left_box)
        left.setContentsMargins(8, 8, 8, 8)
        left.setSpacing(6)
        title = QLabel("World Tempo")
        title.setStyleSheet("font-size: 13px; font-weight: 700; color: #f4f1de;")
        left.addWidget(title)
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
        self.overlay_button = QPushButton("Overlay")
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
        middle.setContentsMargins(8, 8, 8, 8)
        middle.setSpacing(6)
        action_title = QLabel("What You Can Do Now")
        action_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #f4f1de;")
        middle.addWidget(action_title)
        self.context_row = QHBoxLayout()
        self.context_row.setSpacing(8)
        self._action_buttons: list[QPushButton] = []
        middle.addLayout(self.context_row)
        root.addWidget(self.middle_box, stretch=4)

        self.right_box = QFrame()
        self.right_box.setFrameShape(QFrame.Shape.StyledPanel)
        self.right_box.setMaximumWidth(380)
        right = QVBoxLayout(self.right_box)
        right.setContentsMargins(8, 8, 8, 8)
        right.setSpacing(6)
        self.preview_title = QLabel("Likely Effect")
        self.preview_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #f4f1de;")
        self.preview_body = QLabel("Choose an action card to see likely direction, not a guaranteed outcome.")
        self.preview_body.setWordWrap(True)
        self.commit_button = QPushButton("Commit Action")
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
            placeholder = QPushButton("No Immediate Influence")
            placeholder.setEnabled(False)
            placeholder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.context_row.addWidget(placeholder)
            self._action_buttons.append(placeholder)
            self.preview_title.setText("Likely Effect")
            self.preview_body.setText("Shift focus to a visible figure, settlement, power center, or hotspot to act through the formal intervention layer.")
            self.commit_button.setEnabled(False)
            return
        selected_option: InterventionOptionProjection | None = None
        for option in options:
            button = QPushButton(option.label)
            button.setEnabled(option.enabled)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            tone = {
                "support": "#375a7f",
                "stabilize": "#2f6f57",
                "info": "#5a4b7a",
                "mystic": "#80543f",
            }.get(option.emphasis, "#375a7f")
            button.setStyleSheet(f"background-color: {tone}; color: #f7fbff; padding: 10px 12px; border-radius: 8px; font-weight: 700;")
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
