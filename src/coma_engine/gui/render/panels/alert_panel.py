from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from coma_engine.gui.types import AlertItemProjection


class AlertPanel(QWidget):
    def __init__(self, on_select=None):
        super().__init__()
        self.on_select = on_select
        layout = QVBoxLayout(self)
        title = QLabel("Alerts")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #f4f1de;")
        layout.addWidget(title)
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self._handle_click)
        layout.addWidget(self.list_widget)

    def set_alerts(self, alerts: tuple[AlertItemProjection, ...]) -> None:
        self.list_widget.clear()
        for alert in alerts:
            item = QListWidgetItem(alert.title)
            item.setData(32, alert.target_ref)
            item.setData(33, alert.suggested_map_mode)
            item.setToolTip(alert.detail)
            tone = {
                "critical": "#ff7b54",
                "major": "#ffd166",
                "notable": "#b8e986",
            }.get(alert.severity, "#d6e4ff")
            item.setForeground(QColor(tone))
            self.list_widget.addItem(item)

    def _handle_click(self, item: QListWidgetItem) -> None:
        if self.on_select is None:
            return
        target_ref = item.data(32)
        suggested_mode = item.data(33)
        if isinstance(target_ref, str):
            self.on_select(target_ref, suggested_mode)
