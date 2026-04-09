from __future__ import annotations

from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtWidgets import QGraphicsSimpleTextItem

from coma_engine.gui.types import MapMode, TileRenderProjection


def draw_activity_layer(
    scene,
    tile: TileRenderProjection,
    tile_size: int,
    *,
    map_mode: MapMode,
    pulse_phase: float,
    alert_severity: str | None,
) -> None:
    x = tile.x * tile_size
    y = tile.y * tile_size
    if tile.attention_band != "calm":
        alert = {
            "critical": QColor("#ff7b54"),
            "urgent": QColor("#f4d35e"),
            "watch": QColor("#7dd3fc"),
            "calm": QColor("#00000000"),
        }[tile.attention_band]
        pulse_scale = {
            "critical": 1.0,
            "urgent": 0.75,
            "watch": 0.45,
            "calm": 0.0,
        }[tile.attention_band]
        alpha = 78 if map_mode != "world" else 105
        alert.setAlpha(max(35, min(190, int(alpha + pulse_phase * 60 * pulse_scale))))
        halo = scene.addEllipse(x - 4, y - 4, tile_size + 8, tile_size + 8, QPen(QColor("#00000000")), QBrush(alert))
        halo.setData(0, tile.ref)
        halo.setZValue(3)
        outer = QColor(alert)
        outer.setAlpha(max(18, min(110, int(20 + pulse_phase * 42 * pulse_scale))))
        outer_halo = scene.addEllipse(x - 8, y - 8, tile_size + 16, tile_size + 16, QPen(QColor("#00000000")), QBrush(outer))
        outer_halo.setData(0, tile.ref)
        outer_halo.setZValue(2)
    if tile.command_stress_level >= 24.0 or tile.local_unrest >= 32.0:
        strain_color = QColor("#ff6b6b")
        strain_color.setAlpha(max(60, min(180, int(tile.command_stress_level * 1.4))))
        strain_pen = QPen(strain_color)
        strain_pen.setWidth(3 if tile.command_stress_level >= 50.0 else 2)
        strain = scene.addRect(x + 1, y + 1, tile_size - 2, tile_size - 2, strain_pen)
        strain.setData(0, tile.ref)
        strain.setZValue(5)
    if tile.activity_level > 0.0:
        activity_color = QColor("#e9f5db") if tile.known_visibility == "confirmed" else QColor("#9aa8b1")
        activity_color.setAlpha(max(70, min(210, int(90 + tile.activity_level * 0.9))))
        activity = scene.addEllipse(x + 10, y + 10, 12, 12, QPen(QColor("#00000000")), QBrush(activity_color))
        activity.setData(0, tile.ref)
        activity.setZValue(4)
    if tile.signal_level >= 8.0:
        signal = QGraphicsSimpleTextItem("~")
        signal_color = QColor("#8bd3ff")
        signal_color.setAlpha(max(100, min(230, int(90 + tile.signal_level * 4.0 + pulse_phase * 35))))
        signal.setBrush(QBrush(signal_color))
        signal.setPos(x + tile_size - 12, y + 2)
        signal.setData(0, tile.ref)
        scene.addItem(signal)
        signal.setZValue(6)
    if tile.power_level >= 35.0:
        beacon = scene.addEllipse(x + 2, y + tile_size - 8, 6, 6, QPen(QColor("#00000000")), QBrush(QColor("#f7b267")))
        beacon.setData(0, tile.ref)
        beacon.setZValue(6)
    if alert_severity is not None or "major change" in tile.attention_tags:
        marker = QGraphicsSimpleTextItem("!")
        tone = {
            "critical": QColor("#ff9f1c"),
            "major": QColor("#ffe066"),
            "notable": QColor("#b8f2e6"),
            None: QColor("#ffe066"),
        }[alert_severity]
        tone.setAlpha(max(120, min(255, int(150 + pulse_phase * 70))))
        marker.setBrush(QBrush(tone))
        marker.setPos(x + 3, y + 1)
        marker.setData(0, tile.ref)
        scene.addItem(marker)
        marker.setZValue(7)
    text = None
    if tile.settlement_id:
        text = QGraphicsSimpleTextItem("S")
        text.setBrush(QBrush(QColor("#111111")))
        text.setPos(x + 6, y + 3)
        text.setData(0, tile.settlement_id)
    elif tile.attention_band in {"critical", "urgent"}:
        text = QGraphicsSimpleTextItem("!")
        text.setBrush(QBrush(QColor("#fff2d8")))
        text.setPos(x + 10, y + 4)
        text.setData(0, tile.ref)
    if text is not None:
        scene.addItem(text)
        text.setZValue(6)
