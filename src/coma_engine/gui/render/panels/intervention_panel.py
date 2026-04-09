from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from coma_engine.gui.types import InterventionOptionProjection


class InterventionPanel(QWidget):
    def __init__(self, on_action):
        super().__init__()
        self.on_action = on_action
        self.layout = QVBoxLayout(self)
        header = QLabel("What You Can Do")
        header.setStyleSheet("font-size: 16px; font-weight: 700; color: #f4f1de;")
        self.layout.addWidget(header)
        self._cards: list[QWidget] = []

    def set_options(self, options: tuple[InterventionOptionProjection, ...]) -> None:
        for card in self._cards:
            self.layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()
        if not options:
            empty = QLabel("Select a figure, region, or settlement to reveal meaningful interventions.")
            empty.setWordWrap(True)
            self.layout.addWidget(empty)
            self._cards.append(empty)
            return
        for option in options:
            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel)
            accent = {
                "support": "#375a7f",
                "stabilize": "#627a2f",
                "info": "#5f4b8b",
                "mystic": "#8b5f2c",
            }.get(option.emphasis, "#375a7f")
            card.setStyleSheet(
                "QFrame {"
                f" background-color: #18222d; border: 1px solid {accent}; border-radius: 8px;"
                "}"
            )
            card_layout = QVBoxLayout(card)
            title = QLabel(option.label)
            title.setStyleSheet("font-weight: 700; color: #f6f9ff;")
            description = QLabel(option.description)
            description.setWordWrap(True)
            description.setStyleSheet("color: #d1d9e5;")
            impact = QLabel(option.impact_hint)
            impact.setWordWrap(True)
            impact.setStyleSheet("color: #c7d88c; font-size: 11px;")
            button = QPushButton("Commit Intervention")
            button.setEnabled(option.enabled)
            button.setToolTip(option.description)
            button.clicked.connect(lambda _checked=False, action_id=option.action_id, target=option.target_ref: self.on_action(action_id, target))
            card_layout.addWidget(title)
            card_layout.addWidget(description)
            if option.impact_hint:
                card_layout.addWidget(impact)
            card_layout.addWidget(button)
            self.layout.addWidget(card)
            self._cards.append(card)
