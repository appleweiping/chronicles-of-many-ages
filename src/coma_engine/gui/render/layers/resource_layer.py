from __future__ import annotations

from PySide6.QtGui import QColor, QBrush, QPen

from coma_engine.gui.types import MapMode, TileRenderProjection


def draw_resource_layer(scene, tile: TileRenderProjection, tile_size: int, *, map_mode: MapMode) -> None:
    if map_mode not in {"resources", "pressure", "world"}:
        return
    x = tile.x * tile_size
    y = tile.y * tile_size
    if map_mode == "resources":
        level = max(0.0, min(100.0, 100.0 - tile.scarcity_level))
        color = QColor("#80ed99")
        color.setAlpha(max(16, min(130, int(level * 1.2))))
        marker = scene.addEllipse(x + 6, y + 6, tile_size - 12, tile_size - 12, QPen(QColor("#00000000")), QBrush(color))
    elif map_mode == "pressure":
        level = tile.command_stress_level
        color = QColor("#f4a261")
        color.setAlpha(max(16, min(145, int(level * 1.4))))
        marker = scene.addEllipse(x + 6, y + 6, tile_size - 12, tile_size - 12, QPen(QColor("#00000000")), QBrush(color))
    else:
        if tile.scarcity_level < 14.0 and tile.command_stress_level < 18.0:
            return
        stress_height = max(3.0, min(tile_size - 4.0, tile.command_stress_level * 0.12))
        scarcity_width = max(3.0, min(tile_size - 4.0, tile.scarcity_level * 0.1))
        stress_color = QColor("#f28f3b")
        stress_color.setAlpha(max(45, min(135, int(tile.command_stress_level * 1.1))))
        scarcity_color = QColor("#7ae582")
        scarcity_color.setAlpha(max(35, min(120, int(tile.scarcity_level * 0.9))))
        stress = scene.addRect(x + 2, y + tile_size - stress_height - 2, tile_size - 4, stress_height, QPen(QColor("#00000000")), QBrush(stress_color))
        stress.setData(0, tile.ref)
        stress.setZValue(2)
        marker = scene.addRect(x + 2, y + 2, scarcity_width, 4, QPen(QColor("#00000000")), QBrush(scarcity_color))
    marker.setData(0, tile.ref)
    marker.setZValue(2)
