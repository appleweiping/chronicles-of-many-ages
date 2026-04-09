from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from coma_engine.gui.types import InspectionPanelProjection


class InspectorPanel(QWidget):
    def __init__(self, on_affordance=None):
        super().__init__()
        self.on_affordance = on_affordance
        self.setMaximumWidth(340)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        self.title_label = QLabel("Inspector")
        self.title_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #f4f1de;")
        self.tags_label = QLabel("")
        self.tags_label.setWordWrap(True)
        self.tags_label.setStyleSheet("color: #d0d9e3; font-size: 11px;")
        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("color: #d8e1ec; padding: 8px; background-color: #18232f; border-radius: 6px;")

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.scroll.setWidget(self.content)

        self.affordance_box = QFrame()
        self.affordance_box.setFrameShape(QFrame.Shape.StyledPanel)
        affordance_layout = QVBoxLayout(self.affordance_box)
        self.affordance_title = QLabel("Context")
        self.affordance_buttons_layout = QHBoxLayout()
        affordance_layout.addWidget(self.affordance_title)
        affordance_layout.addLayout(self.affordance_buttons_layout)
        self._affordance_buttons: list[QPushButton] = []

        layout.addWidget(self.title_label)
        layout.addWidget(self.tags_label)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.scroll, stretch=1)
        layout.addWidget(self.affordance_box)

    def render_panel(self, panel: InspectionPanelProjection) -> None:
        self.title_label.setText(panel.title)
        self.tags_label.setText("  |  ".join(panel.status_tags))
        self.summary_label.setText(panel.summary)

        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        shown_sections = 0
        for section in panel.sections:
            if section.title.lower() in {"situational summary", "knowledge boundary"}:
                continue
            if shown_sections >= 2:
                break
            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel)
            card.setStyleSheet("QFrame { background-color: #1b2530; border: 1px solid #364656; border-radius: 8px; }")
            card_layout = QVBoxLayout(card)
            header = QLabel(section.title.title())
            header.setStyleSheet("font-weight: 700; color: #dfe7f2;")
            card_layout.addWidget(header)
            for field in section.fields[:3]:
                line = QLabel(field.value)
                line.setWordWrap(True)
                tone = {
                    "confirmed": "#f3f7ff",
                    "inferred": "#d6e6ff",
                    "rumored": "#f1d8a8",
                    "hidden": "#7f8c98",
                }.get(field.visibility, "#f3f7ff")
                line.setStyleSheet(f"color: {tone}; padding-left: 4px; font-size: 11px;")
                card_layout.addWidget(line)
            self.content_layout.addWidget(card)
            shown_sections += 1
        self.content_layout.addStretch(1)

        while self._affordance_buttons:
            button = self._affordance_buttons.pop()
            self.affordance_buttons_layout.removeWidget(button)
            button.deleteLater()
        for affordance in panel.affordances:
            button = QPushButton(affordance)
            button.clicked.connect(lambda _checked=False, label=affordance, ref=panel.ref: self._handle_affordance(label, ref))
            self.affordance_buttons_layout.addWidget(button)
            self._affordance_buttons.append(button)

    def _handle_affordance(self, label: str, ref: str) -> None:
        if self.on_affordance is not None:
            self.on_affordance(label, ref)
