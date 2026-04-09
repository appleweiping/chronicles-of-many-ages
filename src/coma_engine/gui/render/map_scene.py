from __future__ import annotations

from PySide6.QtGui import QColor, QPen, QBrush, QTransform
from PySide6.QtWidgets import QGraphicsScene, QGraphicsSimpleTextItem

from coma_engine.gui.sync.projection_store import ProjectionStore
from coma_engine.gui.types import TileRenderProjection


TILE_SIZE = 28


def _terrain_color(terrain_type: str) -> QColor:
    palette = {
        "plains": QColor("#b8c87a"),
        "forest": QColor("#5d8a52"),
        "hill": QColor("#b89466"),
        "mountain": QColor("#7c7f86"),
        "water": QColor("#5a8bc0"),
    }
    return palette.get(terrain_type, QColor("#999999"))


class MapScene(QGraphicsScene):
    def __init__(self, store: ProjectionStore, on_select):
        super().__init__()
        self.store = store
        self.on_select = on_select
        self.setBackgroundBrush(QColor("#101418"))

    def render_frame(self, active_overlays: set[str], selected_ref: str | None) -> None:
        self.clear()
        frame = self.store.current
        if frame is None:
            return
        for tile in frame.tiles:
            self._draw_tile(tile, active_overlays, selected_ref)

    def _draw_tile(self, tile: TileRenderProjection, active_overlays: set[str], selected_ref: str | None) -> None:
        x = tile.x * TILE_SIZE
        y = tile.y * TILE_SIZE
        base_color = _terrain_color(tile.terrain_type)
        rect = self.addRect(x, y, TILE_SIZE, TILE_SIZE, QPen(QColor("#20252a")), QBrush(base_color))
        rect.setData(0, tile.ref)

        if "control" in active_overlays and tile.controller_polity_id:
            overlay = QColor("#d97a1f")
            overlay.setAlpha(max(30, min(115, int(tile.control_pressure * 1.5))))
            control_rect = self.addRect(x + 3, y + 3, TILE_SIZE - 6, TILE_SIZE - 6, QPen(QColor("#00000000")), QBrush(overlay))
            control_rect.setData(0, tile.ref)

        if "activity" in active_overlays and tile.activity_level > 0.0:
            activity = self.addEllipse(x + 9, y + 9, 10, 10, QPen(QColor("#00000000")), QBrush(QColor("#f2e86d")))
            activity.setData(0, tile.ref)

        if "infoflow" in active_overlays and tile.visibility_strength < 1.0:
            fog = QColor("#0e1116")
            fog.setAlpha(max(40, min(160, int((1.0 - tile.visibility_strength) * 180))))
            fog_rect = self.addRect(x, y, TILE_SIZE, TILE_SIZE, QPen(QColor("#00000000")), QBrush(fog))
            fog_rect.setData(0, tile.ref)

        label = "S" if tile.settlement_id else ""
        if label:
            text = QGraphicsSimpleTextItem(label)
            text.setBrush(QBrush(QColor("#121212")))
            text.setPos(x + 8, y + 4)
            text.setData(0, tile.ref)
            self.addItem(text)

        if selected_ref == tile.ref:
            selection_pen = QPen(QColor("#f5f7fb"))
            selection_pen.setWidth(2)
            selected = self.addRect(x + 1, y + 1, TILE_SIZE - 2, TILE_SIZE - 2, selection_pen)
            selected.setData(0, tile.ref)

    def mousePressEvent(self, event):  # type: ignore[override]
        item = self.itemAt(event.scenePos(), QTransform())
        ref = item.data(0) if item is not None else None
        self.on_select(ref)
        super().mousePressEvent(event)
