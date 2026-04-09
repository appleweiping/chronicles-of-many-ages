from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QVBoxLayout, QWidget


class OverlayPanel(QWidget):
    def __init__(self, on_toggle, initial_active: set[str]):
        super().__init__()
        layout = QVBoxLayout(self)
        self._checkboxes: dict[str, QCheckBox] = {}
        for name in ("terrain", "control", "activity", "infoflow"):
            checkbox = QCheckBox(name)
            checkbox.setChecked(name in initial_active)
            checkbox.toggled.connect(lambda checked, overlay=name: on_toggle(overlay, checked))
            layout.addWidget(checkbox)
            self._checkboxes[name] = checkbox
