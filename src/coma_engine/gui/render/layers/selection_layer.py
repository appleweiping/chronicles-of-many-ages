from __future__ import annotations

from PySide6.QtGui import QColor, QBrush, QPen

from coma_engine.gui.types import TileRenderProjection


def draw_selection_layer(
    scene,
    tile: TileRenderProjection,
    tile_size: int,
    *,
    selected_ref: str | None,
    selected_action_id: str | None,
    selected_action_target_ref: str | None,
    preview_tile_refs: set[str],
    response_effects: dict[str, str],
    pulse_phase: float,
) -> None:
    related_refs = {tile.ref, tile.settlement_id, tile.controller_polity_id}
    in_selection = selected_ref in related_refs or selected_action_target_ref in related_refs
    in_preview = tile.ref in preview_tile_refs
    in_response = tile.ref in response_effects
    if not in_selection and not in_preview and not in_response:
        return
    x = tile.x * tile_size
    y = tile.y * tile_size
    if in_preview and selected_action_id is not None:
        preview_tone = {
            "resource": QColor("#7ae582"),
            "rumor": QColor("#7dd3fc"),
            "miracle": QColor("#ffb703"),
            "bless": QColor("#f1faee"),
        }.get(selected_action_id, QColor("#9fb3c8"))
        preview_tone.setAlpha(max(28, min(95, int(40 + pulse_phase * 38))))
        preview = scene.addRect(x + 3, y + 3, tile_size - 6, tile_size - 6, QPen(QColor("#00000000")), QBrush(preview_tone))
        preview.setData(0, tile.ref)
        preview.setZValue(6.5)
    if selected_action_id is not None and selected_action_target_ref in related_refs:
        tone = {
            "resource": QColor("#7ae582"),
            "rumor": QColor("#7dd3fc"),
            "miracle": QColor("#ffb703"),
            "bless": QColor("#f1faee"),
        }.get(selected_action_id, QColor("#9fb3c8"))
        tone.setAlpha(95)
        context = scene.addEllipse(x + 4, y + 4, tile_size - 8, tile_size - 8, QPen(QColor("#00000000")), QBrush(tone))
        context.setData(0, tile.ref)
        context.setZValue(7)
    if in_response:
        response_action = response_effects[tile.ref]
        response_tone = {
            "resource": QColor("#9ef01a"),
            "rumor": QColor("#90e0ef"),
            "miracle": QColor("#ffd166"),
            "bless": QColor("#f1faee"),
        }.get(response_action, QColor("#cddafd"))
        response_tone.setAlpha(max(55, min(180, int(85 + pulse_phase * 65))))
        flash_pen = QPen(response_tone)
        flash_pen.setWidth(3)
        flash = scene.addEllipse(x + 2, y + 2, tile_size - 4, tile_size - 4, flash_pen)
        flash.setData(0, tile.ref)
        flash.setOpacity(0.5 + pulse_phase * 0.35)
        flash.setZValue(7.5)
    selection_pen = QPen(QColor("#f5f7fb"))
    selection_pen.setWidth(3 if selected_ref == tile.ref else 2)
    selected = scene.addRect(x + 1, y + 1, tile_size - 2, tile_size - 2, selection_pen)
    selected.setData(0, tile.ref)
    selected.setZValue(8)
