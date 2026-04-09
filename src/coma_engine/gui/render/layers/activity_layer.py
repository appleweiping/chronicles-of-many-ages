from __future__ import annotations

from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtWidgets import QGraphicsSimpleTextItem

from coma_engine.gui.types import MapMode, TileRenderProjection


def draw_activity_layer(scene, tile: TileRenderProjection, tile_size: int, *, map_mode: MapMode) -> None:
    x = tile.x * tile_size
    y = tile.y * tile_size
    if tile.attention_band != "calm":
        alert = {
            "critical": QColor("#ff7b54"),
            "urgent": QColor("#f4d35e"),
            "watch": QColor("#7dd3fc"),
            "calm": QColor("#00000000"),
        }[tile.attention_band]
        alert.setAlpha(110 if map_mode == "world" else 80)
        halo = scene.addEllipse(x - 2, y - 2, tile_size + 4, tile_size + 4, QPen(QColor("#00000000")), QBrush(alert))
        halo.setData(0, tile.ref)
        halo.setZValue(3)
    if tile.activity_level > 0.0:
        activity_color = QColor("#e9f5db") if tile.known_visibility == "confirmed" else QColor("#9aa8b1")
        activity = scene.addEllipse(x + 9, y + 9, 10, 10, QPen(QColor("#00000000")), QBrush(activity_color))
        activity.setData(0, tile.ref)
        activity.setZValue(4)
    text = None
    if tile.settlement_id:
        text = QGraphicsSimpleTextItem("S")
        text.setBrush(QBrush(QColor("#111111")))
        text.setPos(x + 8, y + 4)
        text.setData(0, tile.settlement_id)
    elif tile.attention_band in {"critical", "urgent"}:
        text = QGraphicsSimpleTextItem("!")
        text.setBrush(QBrush(QColor("#fff2d8")))
        text.setPos(x + 9, y + 4)
        text.setData(0, tile.ref)
    if text is not None:
        scene.addItem(text)
        text.setZValue(6)
