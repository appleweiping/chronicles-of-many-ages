from __future__ import annotations

from PySide6.QtGui import QColor, QPen

from coma_engine.gui.types import InfoFlowProjection, MapMode, TileRenderProjection


def draw_infoflow_layer(
    scene,
    tiles: tuple[TileRenderProjection, ...],
    info_flows: tuple[InfoFlowProjection, ...],
    tile_size: int,
    *,
    map_mode: MapMode,
    enabled: bool,
    pulse_phase: float,
) -> None:
    if not enabled and map_mode != "infoflow":
        return
    tile_lookup = {tile.ref: tile for tile in tiles}
    for flow in info_flows[-18:]:
        if flow.location_ref is None or flow.location_ref not in tile_lookup:
            continue
        tile = tile_lookup[flow.location_ref]
        x = tile.x * tile_size + tile_size / 2
        y = tile.y * tile_size + tile_size / 2
        line_length = max(8.0, min(22.0, flow.strength * 0.3))
        color = QColor("#7dd3fc" if flow.content_domain != "command" else "#4ea8de")
        color.setAlpha(max(85, min(225, int(150 + pulse_phase * 45 - flow.distortion * 45))))
        pen = QPen(color)
        pen.setWidth(2 if map_mode == "infoflow" else 1 + int(pulse_phase > 0.7))
        if flow.content_domain == "command":
            start_x, start_y = x, y - line_length / 2
            end_x, end_y = x, y + line_length / 2
            arrow_left = scene.addLine(end_x, end_y, end_x - 3, end_y - 5, pen)
            arrow_right = scene.addLine(end_x, end_y, end_x + 3, end_y - 5, pen)
            arrow_left.setData(0, flow.location_ref)
            arrow_right.setData(0, flow.location_ref)
            arrow_left.setZValue(5)
            arrow_right.setZValue(5)
        elif flow.content_domain == "belief":
            start_x, start_y = x - line_length / 2, y - 2
            end_x, end_y = x + line_length / 2, y + 2
        else:
            start_x, start_y = x - line_length / 2, y + 3
            end_x, end_y = x + line_length / 2, y - 3
        trail = scene.addLine(start_x, start_y, end_x, end_y, pen)
        trail.setData(0, flow.location_ref)
        trail.setZValue(5)
        echo = scene.addLine(start_x - 2, start_y + 2, end_x - 2, end_y + 2, pen)
        echo.setData(0, flow.location_ref)
        echo.setOpacity(0.45)
        echo.setZValue(4)
