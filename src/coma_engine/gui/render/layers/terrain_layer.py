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
    if tile.change_direction == "rising" and tile.change_intensity >= 6.0:
        base_color = base_color.lighter(108)
    elif tile.change_direction == "falling" and tile.change_intensity >= 6.0:
        base_color = base_color.darker(108)
    if tile.attention_band in {"urgent", "critical"}:
        base_color = base_color.lighter(104)
    if tile.known_visibility != "confirmed":
        base_color = base_color.darker(135)
    rect = scene.addRect(x, y, tile_size, tile_size, QPen(QColor("#1c252d")), QBrush(base_color))
    rect.setData(0, tile.ref)
    rect.setZValue(0)
    if enabled and (tile.change_intensity >= 9.0 or tile.signal_level >= 10.0):
        shift = QColor("#ff7b54" if tile.change_direction == "rising" else "#7dd3fc")
        shift.setAlpha(max(18, min(65, int(tile.change_intensity * 3.0 + tile.signal_level * 1.2))))
        overlay = scene.addRect(x + 1, y + 1, tile_size - 2, tile_size - 2, QPen(QColor("#00000000")), QBrush(shift))
        overlay.setData(0, tile.ref)
        overlay.setZValue(0.5)
