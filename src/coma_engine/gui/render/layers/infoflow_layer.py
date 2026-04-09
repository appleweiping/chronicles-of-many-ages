from __future__ import annotations

from PySide6.QtGui import QColor, QPen

from coma_engine.gui.types import InfoFlowProjection, MapMode, TileRenderProjection


def draw_infoflow_layer(scene, tiles: tuple[TileRenderProjection, ...], info_flows: tuple[InfoFlowProjection, ...], tile_size: int, *, map_mode: MapMode, enabled: bool) -> None:
    if not enabled and map_mode != "infoflow":
        return
    tile_lookup = {tile.ref: tile for tile in tiles}
    for flow in info_flows[-18:]:
        if flow.location_ref is None or flow.location_ref not in tile_lookup:
            continue
        tile = tile_lookup[flow.location_ref]
        x = tile.x * tile_size + tile_size / 2
        y = tile.y * tile_size + tile_size / 2
        line_length = max(6.0, min(18.0, flow.strength * 0.25))
        color = QColor("#7dd3fc" if flow.content_domain != "command" else "#4ea8de")
        color.setAlpha(max(55, min(180, int(140 - flow.distortion * 60))))
        pen = QPen(color)
        pen.setWidth(2 if map_mode == "infoflow" else 1)
        line = scene.addLine(x - line_length / 2, y, x + line_length / 2, y, pen)
        line.setData(0, flow.location_ref)
        line.setZValue(5)
