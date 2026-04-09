from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from coma_engine.gui.types import InterventionOptionProjection


class InterventionPanel(QWidget):
    def __init__(self, on_action):
        super().__init__()
        self.on_action = on_action
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(QLabel("Interventions"))
        self._buttons: list[QPushButton] = []

    def set_options(self, options: tuple[InterventionOptionProjection, ...]) -> None:
        for button in self._buttons:
            self.layout.removeWidget(button)
            button.deleteLater()
        self._buttons.clear()
        for option in options:
            button = QPushButton(option.label)
            button.setEnabled(option.enabled)
            button.setToolTip(option.description)
            button.clicked.connect(lambda _checked=False, action_id=option.action_id, target=option.target_ref: self.on_action(action_id, target))
            self.layout.addWidget(button)
            self._buttons.append(button)
