from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from coma_engine.gui.types import InspectionPanelProjection


class InspectorPanel(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.title_label = QLabel("Inspector")
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.text)

    def render_panel(self, panel: InspectionPanelProjection) -> None:
        self.title_label.setText(panel.title)
        lines: list[str] = []
        for section in panel.sections:
            lines.append(f"[{section.title}]")
            for field in section.fields:
                lines.append(f"{field.label}. {field.value}")
            lines.append("")
        self.text.setPlainText("\n".join(lines).strip())
