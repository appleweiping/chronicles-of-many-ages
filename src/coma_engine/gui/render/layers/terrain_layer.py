from __future__ import annotations

from PySide6.QtGui import QColor, QBrush, QPen

from coma_engine.gui.types import TileRenderProjection


def terrain_color(terrain_type: str) -> QColor:
    palette = {
        "plains": QColor("#6f8754"),
        "forest": QColor("#2f5d50"),
        "hill": QColor("#8b6b4d"),
        "mountain": QColor("#616773"),
        "water": QColor("#355c8a"),
    }
    return palette.get(terrain_type, QColor("#999999"))


def draw_terrain_layer(scene, tile: TileRenderProjection, tile_size: int, *, enabled: bool) -> None:
    x = tile.x * tile_size
    y = tile.y * tile_size
    base_color = terrain_color(tile.terrain_type) if enabled else QColor("#25313d")
    if tile.known_visibility != "confirmed":
        base_color = base_color.darker(135)
    rect = scene.addRect(x, y, tile_size, tile_size, QPen(QColor("#1c252d")), QBrush(base_color))
    rect.setData(0, tile.ref)
    rect.setZValue(0)
