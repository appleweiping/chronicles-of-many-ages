from __future__ import annotations

from PySide6.QtGui import QColor, QPen, QBrush, QTransform
from PySide6.QtWidgets import QGraphicsScene

from coma_engine.gui.render.layers import (
    draw_activity_layer,
    draw_control_layer,
    draw_infoflow_layer,
    draw_resource_layer,
    draw_selection_layer,
    draw_terrain_layer,
)
from coma_engine.gui.sync.projection_store import ProjectionStore
from coma_engine.gui.types import MapMode, TileRenderProjection


TILE_SIZE = 28


class MapScene(QGraphicsScene):
    def __init__(self, store: ProjectionStore, on_select):
        super().__init__()
        self.store = store
        self.on_select = on_select
        self.setBackgroundBrush(QColor("#101418"))

    def render_frame(self, active_overlays: set[str], selected_ref: str | None, map_mode: MapMode = "world") -> None:
        self.clear()
        frame = self.store.current
        if frame is None:
            return
        if frame.tiles:
            width = (max(tile.x for tile in frame.tiles) + 1) * TILE_SIZE
            height = (max(tile.y for tile in frame.tiles) + 1) * TILE_SIZE
            self.setSceneRect(0, 0, width, height)
        for tile in frame.tiles:
            self._draw_tile(tile, active_overlays, selected_ref, map_mode)
        draw_infoflow_layer(self, frame.tiles, frame.info_flows, TILE_SIZE, map_mode=map_mode, enabled="signals" in active_overlays)

    def _draw_tile(self, tile: TileRenderProjection, active_overlays: set[str], selected_ref: str | None, map_mode: MapMode) -> None:
        draw_terrain_layer(self, tile, TILE_SIZE, enabled="terrain" in active_overlays or map_mode == "world")
        draw_control_layer(self, tile, TILE_SIZE, map_mode=map_mode)
        draw_resource_layer(self, tile, TILE_SIZE, map_mode=map_mode)
        draw_activity_layer(self, tile, TILE_SIZE, map_mode=map_mode)
        if "fog" in active_overlays and tile.known_visibility != "confirmed":
            x = tile.x * TILE_SIZE
            y = tile.y * TILE_SIZE
            fog = QColor("#0e1116")
            fog.setAlpha(90 if tile.known_visibility == "rumored" else 135)
            fog_rect = self.addRect(x, y, TILE_SIZE, TILE_SIZE, QPen(QColor("#00000000")), QBrush(fog))
            fog_rect.setData(0, tile.ref)
            fog_rect.setZValue(7)
        draw_selection_layer(self, tile, TILE_SIZE, selected_ref=selected_ref)

    def mousePressEvent(self, event):  # type: ignore[override]
        item = self.itemAt(event.scenePos(), QTransform())
        ref = item.data(0) if item is not None else None
        self.on_select(ref)
        super().mousePressEvent(event)
