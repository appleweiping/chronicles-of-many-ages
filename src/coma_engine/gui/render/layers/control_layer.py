from __future__ import annotations

from PySide6.QtGui import QColor, QBrush, QPen

from coma_engine.gui.types import MapMode, TileRenderProjection


def draw_control_layer(scene, tile: TileRenderProjection, tile_size: int, *, map_mode: MapMode) -> None:
    if tile.power_level <= 0.0:
        return
    alpha = max(18, min(140, int(tile.power_level * (2.5 if map_mode == "control" else 1.4))))
    overlay = QColor("#4ea8de" if map_mode == "control" else "#ef8354")
    overlay.setAlpha(alpha)
    x = tile.x * tile_size
    y = tile.y * tile_size
    control_rect = scene.addRect(
        x + 4,
        y + 4,
        tile_size - 8,
        tile_size - 8,
        QPen(QColor("#00000000")),
        QBrush(overlay),
    )
    control_rect.setData(0, tile.settlement_id or tile.controller_polity_id or tile.ref)
    control_rect.setZValue(1)
