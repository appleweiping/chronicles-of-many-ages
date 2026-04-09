from __future__ import annotations

import math

from PySide6.QtGui import QColor, QPen, QBrush, QTransform
from PySide6.QtWidgets import QGraphicsScene

from coma_engine.gui.render.layers import (
    draw_activity_layer,
    draw_control_layer,
    draw_dynamics_layer,
    draw_infoflow_layer,
    draw_resource_layer,
    draw_selection_layer,
    draw_terrain_layer,
)
from coma_engine.gui.sync.projection_store import ProjectionStore
from coma_engine.gui.types import AlertItemProjection
from coma_engine.gui.types import MapMode, TileRenderProjection


TILE_SIZE = 32


class MapScene(QGraphicsScene):
    def __init__(self, store: ProjectionStore, on_select):
        super().__init__()
        self.store = store
        self.on_select = on_select
        self.setBackgroundBrush(QColor("#101418"))
        self._pulse_step = 0
        self._last_active_overlays: set[str] = set()
        self._last_selected_ref: str | None = None
        self._last_map_mode: MapMode = "world"
        self._last_alerts: tuple[AlertItemProjection, ...] = ()
        self._last_alert_tile_severities: tuple[tuple[str, str], ...] = ()
        self._last_selected_action_id: str | None = None
        self._last_selected_action_target_ref: str | None = None
        self._last_preview_tile_refs: tuple[str, ...] = ()
        self._last_response_effects: tuple[tuple[str, str], ...] = ()

    def render_frame(
        self,
        active_overlays: set[str],
        selected_ref: str | None,
        map_mode: MapMode = "world",
        *,
        alerts: tuple[AlertItemProjection, ...] = (),
        alert_tile_severities: tuple[tuple[str, str], ...] = (),
        selected_action_id: str | None = None,
        selected_action_target_ref: str | None = None,
        preview_tile_refs: tuple[str, ...] = (),
        response_effects: tuple[tuple[str, str], ...] = (),
    ) -> None:
        self._last_active_overlays = set(active_overlays)
        self._last_selected_ref = selected_ref
        self._last_map_mode = map_mode
        self._last_alerts = alerts
        self._last_alert_tile_severities = alert_tile_severities
        self._last_selected_action_id = selected_action_id
        self._last_selected_action_target_ref = selected_action_target_ref
        self._last_preview_tile_refs = preview_tile_refs
        self._last_response_effects = response_effects
        self.clear()
        frame = self.store.current
        if frame is None:
            return
        self._pulse_step = (self._pulse_step + 1) % 24
        pulse_phase = (math.sin((self._pulse_step / 24.0) * math.tau) + 1.0) / 2.0
        alert_lookup = {tile_ref: severity for tile_ref, severity in alert_tile_severities}
        preview_tile_ref_set = set(preview_tile_refs)
        response_effect_lookup = {tile_ref: action_id for tile_ref, action_id in response_effects}
        for alert in alerts:
            if alert.target_ref is not None and alert.target_ref not in alert_lookup:
                alert_lookup[alert.target_ref] = alert.severity
        if frame.tiles:
            width = (max(tile.x for tile in frame.tiles) + 1) * TILE_SIZE
            height = (max(tile.y for tile in frame.tiles) + 1) * TILE_SIZE
            self.setSceneRect(0, 0, width, height)
        for tile in frame.tiles:
            self._draw_tile(
                tile,
                active_overlays,
                selected_ref,
                map_mode,
                alert_lookup.get(tile.ref),
                selected_action_id,
                selected_action_target_ref,
                preview_tile_ref_set,
                response_effect_lookup,
                pulse_phase,
            )
        draw_dynamics_layer(
            self,
            frame.tiles,
            TILE_SIZE,
            map_mode=map_mode,
            pulse_phase=pulse_phase,
            dynamic_hotspots=frame.dynamic_hotspots,
        )
        draw_infoflow_layer(
            self,
            frame.tiles,
            frame.info_flows,
            TILE_SIZE,
            map_mode=map_mode,
            enabled="signals" in active_overlays,
            pulse_phase=pulse_phase,
        )

    def advance_animation(self) -> None:
        if self.store.current is None:
            return
        self.render_frame(
            self._last_active_overlays,
            self._last_selected_ref,
            self._last_map_mode,
            alerts=self._last_alerts,
            alert_tile_severities=self._last_alert_tile_severities,
            selected_action_id=self._last_selected_action_id,
            selected_action_target_ref=self._last_selected_action_target_ref,
            preview_tile_refs=self._last_preview_tile_refs,
            response_effects=self._last_response_effects,
        )

    def _draw_tile(
        self,
        tile: TileRenderProjection,
        active_overlays: set[str],
        selected_ref: str | None,
        map_mode: MapMode,
        alert_severity: str | None,
        selected_action_id: str | None,
        selected_action_target_ref: str | None,
        preview_tile_ref_set: set[str],
        response_effect_lookup: dict[str, str],
        pulse_phase: float,
    ) -> None:
        draw_terrain_layer(self, tile, TILE_SIZE, enabled="terrain" in active_overlays or map_mode == "world")
        draw_control_layer(self, tile, TILE_SIZE, map_mode=map_mode)
        draw_resource_layer(self, tile, TILE_SIZE, map_mode=map_mode)
        draw_activity_layer(
            self,
            tile,
            TILE_SIZE,
            map_mode=map_mode,
            pulse_phase=pulse_phase,
            alert_severity=alert_severity,
        )
        if "fog" in active_overlays and tile.known_visibility != "confirmed":
            x = tile.x * TILE_SIZE
            y = tile.y * TILE_SIZE
            fog = QColor("#0e1116")
            fog.setAlpha(90 if tile.known_visibility == "rumored" else 135)
            fog_rect = self.addRect(x, y, TILE_SIZE, TILE_SIZE, QPen(QColor("#00000000")), QBrush(fog))
            fog_rect.setData(0, tile.ref)
            fog_rect.setZValue(7)
        draw_selection_layer(
            self,
            tile,
            TILE_SIZE,
            selected_ref=selected_ref,
            selected_action_id=selected_action_id,
            selected_action_target_ref=selected_action_target_ref,
            preview_tile_refs=preview_tile_ref_set,
            response_effects=response_effect_lookup,
            pulse_phase=pulse_phase,
        )

    def mousePressEvent(self, event):  # type: ignore[override]
        item = self.itemAt(event.scenePos(), QTransform())
        ref = item.data(0) if item is not None else None
        self.on_select(ref)
        super().mousePressEvent(event)
