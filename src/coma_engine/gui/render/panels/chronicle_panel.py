from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from coma_engine.gui.types import ChronicleItemProjection, TimelineGroupProjection


class ChroniclePanel(QWidget):
    def __init__(self, on_select=None):
        super().__init__()
        self.on_select = on_select
        self._chronicle_items: tuple[ChronicleItemProjection, ...] = ()
        self._history_groups: tuple[TimelineGroupProjection, ...] = ()
        self._show_history = False
        layout = QVBoxLayout(self)
        self.title = QLabel("Chronicle")
        self.title.setStyleSheet("font-size: 16px; font-weight: 700; color: #f4f1de;")
        self.toggle_button = QPushButton("Show Historical Nodes")
        self.toggle_button.clicked.connect(self._toggle_mode)
        layout.addWidget(self.title)
        layout.addWidget(self.toggle_button)
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self._handle_click)
        layout.addWidget(self.list_widget)

    def set_items(self, items: tuple[ChronicleItemProjection, ...]) -> None:
        self._chronicle_items = items
        if not self._show_history:
            self._render_current()

    def set_history_groups(self, groups: tuple[TimelineGroupProjection, ...]) -> None:
        self._history_groups = groups
        if self._show_history:
            self._render_current()

    def _toggle_mode(self) -> None:
        self._show_history = not self._show_history
        self._render_current()

    def _render_current(self) -> None:
        self.list_widget.clear()
        if self._show_history:
            self.title.setText("Historical Nodes")
            self.toggle_button.setText("Show Chronicle")
            for group in self._history_groups:
                header = QListWidgetItem(group.title)
                header.setForeground(QColor("#ffd166"))
                self.list_widget.addItem(header)
                for row in group.rows:
                    item = QListWidgetItem(f"  {row.headline} — {row.detail}")
                    item.setData(32, row.target_ref)
                    tone = {
                        "major": "#ffd166",
                        "notable": "#d6e4ff",
                        "rumor": "#d0bdf4",
                    }.get(row.tone, "#d6e4ff")
                    item.setForeground(QColor(tone))
                    self.list_widget.addItem(item)
            return

        self.title.setText("Chronicle")
        self.toggle_button.setText("Show Historical Nodes")
        for row in self._chronicle_items:
            item = QListWidgetItem(f"{row.headline} — {row.detail}")
            item.setData(32, row.target_ref)
            tone = {
                "regional": "#d6e4ff",
                "civilization": "#ffd166",
                "rumor": "#d0bdf4",
            }.get(row.tone, "#d6e4ff")
            item.setForeground(QColor(tone))
            self.list_widget.addItem(item)

    def _handle_click(self, item: QListWidgetItem) -> None:
        if self.on_select is None:
            return
        target_ref = item.data(32)
        if isinstance(target_ref, str):
            self.on_select(target_ref)
