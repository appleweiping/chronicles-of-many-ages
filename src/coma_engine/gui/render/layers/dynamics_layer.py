from __future__ import annotations

from PySide6.QtGui import QColor, QPen

from coma_engine.gui.types import MapMode, TileRenderProjection


def draw_dynamics_layer(
    scene,
    tiles: tuple[TileRenderProjection, ...],
    tile_size: int,
    *,
    map_mode: MapMode,
    pulse_phase: float,
    dynamic_hotspots: tuple[str, ...],
) -> None:
    tile_lookup = {(tile.x, tile.y): tile for tile in tiles}
    hotspot_refs = set(dynamic_hotspots)
    for tile in tiles:
        if tile.known_visibility == "hidden":
            continue
        center_x = tile.x * tile_size + tile_size / 2
        center_y = tile.y * tile_size + tile_size / 2
        if tile.ref in hotspot_refs:
            hotspot_color = QColor("#ffb703" if tile.change_direction == "rising" else "#90e0ef")
            hotspot_color.setAlpha(max(22, min(95, int(30 + pulse_phase * 35 + tile.change_intensity * 1.1))))
            field = scene.addEllipse(center_x - tile_size * 0.9, center_y - tile_size * 0.9, tile_size * 1.8, tile_size * 1.8, QPen(QColor("#00000000")), hotspot_color)
            field.setData(0, tile.ref)
            field.setZValue(1)
            ripple_color = QColor(hotspot_color)
            ripple_color.setAlpha(max(25, min(90, int(20 + pulse_phase * 45))))
            ripple_pen = QPen(ripple_color)
            ripple_pen.setWidth(2)
            ring = scene.addEllipse(center_x - tile_size * (1.1 + pulse_phase * 0.15), center_y - tile_size * (1.1 + pulse_phase * 0.15), tile_size * (2.2 + pulse_phase * 0.3), tile_size * (2.2 + pulse_phase * 0.3), ripple_pen)
            ring.setData(0, tile.ref)
            ring.setOpacity(0.45 + pulse_phase * 0.2)
            ring.setZValue(1)
        if tile.change_direction == "rising" and (tile.pressure_delta >= 4.0 or tile.signal_delta >= 3.0):
            color = QColor("#ff7b54" if tile.pressure_delta >= tile.signal_delta else "#7dd3fc")
            color.setAlpha(max(35, min(140, int(45 + pulse_phase * 55 + tile.change_intensity * 1.4))))
            pen = QPen(color)
            pen.setWidth(2 if map_mode == "world" else 1)
            for dx, dy in ((1, 0), (0, 1)):
                neighbor = tile_lookup.get((tile.x + dx, tile.y + dy))
                if neighbor is None or neighbor.known_visibility == "hidden":
                    continue
                if neighbor.change_direction != "rising" and neighbor.attention_band == "calm":
                    continue
                if neighbor.command_stress_level < 24.0 and neighbor.signal_level < 8.0 and neighbor.attention_score < 30.0:
                    continue
                end_x = neighbor.x * tile_size + tile_size / 2
                end_y = neighbor.y * tile_size + tile_size / 2
                line = scene.addLine(center_x, center_y, end_x, end_y, pen)
                line.setData(0, tile.ref)
                line.setOpacity(0.32 + pulse_phase * 0.18)
                line.setZValue(2)
        if tile.change_intensity >= 8.0:
            trend_color = QColor("#ffe066" if tile.change_direction == "rising" else "#9ad1d4")
            trend_color.setAlpha(max(55, min(180, int(65 + tile.change_intensity * 3.5))))
            pen = QPen(trend_color)
            pen.setWidth(2)
            if tile.change_direction == "rising":
                marker = scene.addLine(center_x - 5, center_y + 5, center_x + 5, center_y - 5, pen)
            elif tile.change_direction == "falling":
                marker = scene.addLine(center_x - 5, center_y - 5, center_x + 5, center_y + 5, pen)
            else:
                marker = scene.addLine(center_x - 5, center_y, center_x + 5, center_y, pen)
            marker.setData(0, tile.ref)
            marker.setZValue(6)
