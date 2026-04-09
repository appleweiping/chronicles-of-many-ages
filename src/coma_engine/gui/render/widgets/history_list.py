from __future__ import annotations

from PySide6.QtWidgets import QListWidget


class HistoryList(QListWidget):
    def set_lines(self, lines: list[str]) -> None:
        self.clear()
        self.addItems(lines)
