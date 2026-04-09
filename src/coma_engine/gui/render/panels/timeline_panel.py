from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from coma_engine.gui.types import TimelineGroupProjection


class TimelinePanel(QWidget):
    def __init__(self, on_select=None, title: str = "Timeline"):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(title))
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        self.on_select = on_select
        self.list_widget.itemClicked.connect(self._handle_click)

    def set_groups(self, groups: tuple[TimelineGroupProjection, ...]) -> None:
        self.list_widget.clear()
        for group in groups:
            header = QListWidgetItem(group.title)
            header.setFlags(header.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.list_widget.addItem(header)
            for row in group.rows:
                item = QListWidgetItem(f"  {row.headline} — {row.detail}")
                item.setData(32, row.target_ref)
                tone = {
                    "major": "#ffd166",
                    "notable": "#d6e4ff",
                    "rumor": "#cdb4db",
                }.get(row.tone, "#d6e4ff")
                item.setForeground(QColor(tone))
                self.list_widget.addItem(item)

    def set_lines(self, lines: list[str]) -> None:
        self.list_widget.clear()
        self.list_widget.addItems(lines)

    def _handle_click(self, item: QListWidgetItem) -> None:
        if self.on_select is None:
            return
        target_ref = item.data(32)
        if isinstance(target_ref, str):
            self.on_select(target_ref)
