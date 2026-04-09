from __future__ import annotations

from PySide6.QtGui import QColor, QPen

from coma_engine.gui.types import TileRenderProjection


def draw_selection_layer(scene, tile: TileRenderProjection, tile_size: int, *, selected_ref: str | None) -> None:
    if selected_ref not in {tile.ref, tile.settlement_id, tile.controller_polity_id}:
        return
    x = tile.x * tile_size
    y = tile.y * tile_size
    selection_pen = QPen(QColor("#f5f7fb"))
    selection_pen.setWidth(2)
    selected = scene.addRect(x + 1, y + 1, tile_size - 2, tile_size - 2, selection_pen)
    selected.setData(0, tile.ref)
    selected.setZValue(8)
