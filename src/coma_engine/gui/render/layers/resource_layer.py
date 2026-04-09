from __future__ import annotations

from PySide6.QtGui import QColor, QBrush, QPen

from coma_engine.gui.types import MapMode, TileRenderProjection


def draw_resource_layer(scene, tile: TileRenderProjection, tile_size: int, *, map_mode: MapMode) -> None:
    if map_mode not in {"resources", "pressure"}:
        return
    x = tile.x * tile_size
    y = tile.y * tile_size
    if map_mode == "resources":
        level = max(0.0, min(100.0, 100.0 - tile.scarcity_level))
        color = QColor("#80ed99")
        color.setAlpha(max(16, min(130, int(level * 1.2))))
    else:
        level = tile.command_stress_level
        color = QColor("#f4a261")
        color.setAlpha(max(16, min(145, int(level * 1.4))))
    marker = scene.addEllipse(x + 6, y + 6, tile_size - 12, tile_size - 12, QPen(QColor("#00000000")), QBrush(color))
    marker.setData(0, tile.ref)
    marker.setZValue(2)
