from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from coma_engine.gui.interaction import (
    CameraController,
    CommandRouter,
    InterventionController,
    OverlayController,
    SelectionController,
    TimeController,
)
from coma_engine.gui.presentation import (
    build_alert_stack,
    build_chronicle_stream,
    build_debug_lines,
    build_inspection_panel,
    build_intervention_options,
    build_timeline_groups,
    build_top_bar,
    pick_default_focus_ref,
)
from coma_engine.gui.render.map_scene import MapScene
from coma_engine.gui.render.map_view import MapView
from coma_engine.gui.render.panels.action_ribbon import ActionRibbon
from coma_engine.gui.render.panels.alert_panel import AlertPanel
from coma_engine.gui.render.panels.chronicle_panel import ChroniclePanel
from coma_engine.gui.render.panels.inspector_panel import InspectorPanel
from coma_engine.gui.render.panels.timeline_panel import TimelinePanel
from coma_engine.gui.render.panels.top_bar import TopBar
from coma_engine.gui.session import GuiSession


class MainWindow(QMainWindow):
    def __init__(self, session: GuiSession):
        super().__init__()
        self.session = session
        self.setWindowTitle("Chronicles of Many Ages")
        self.resize(1540, 960)

        self.selection = SelectionController(session)
        self.camera = CameraController(session)
        self.time = TimeController(session)
        self.overlays = OverlayController(session)
        self.interventions = InterventionController(session)
        self.commands = CommandRouter(self.interventions)
        self._animation_tick = 0
        self._recent_action_feedback: list[dict[str, object]] = []

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)
        self.setCentralWidget(root)
        self.setStyleSheet(
            "QMainWindow, QWidget { background-color: #0d1318; color: #e7ecf2; }"
            "QFrame { border: 1px solid #24313b; background-color: #131b22; border-radius: 10px; }"
            "QLabel { color: #e7ecf2; }"
            "QPushButton { background-color: #233341; color: #f6f8fb; padding: 6px 10px; border-radius: 8px; border: 1px solid #314656; }"
            "QPushButton:hover { background-color: #2c4254; }"
            "QPushButton:disabled { color: #738393; background-color: #182028; border-color: #22303d; }"
            "QListWidget { background-color: #111920; border: 1px solid #263744; border-radius: 8px; }"
        )

        self.top_bar = TopBar(self._step_once, self._pause, self._resume)
        root_layout.addWidget(self.top_bar)

        stage_shell = QWidget()
        stage_layout = QHBoxLayout(stage_shell)
        stage_layout.setContentsMargins(0, 0, 0, 0)
        stage_layout.setSpacing(8)
        root_layout.addWidget(stage_shell, stretch=6)

        self.left_column = QWidget()
        self.left_column.setMinimumWidth(132)
        self.left_column.setMaximumWidth(170)
        left_layout = QVBoxLayout(self.left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        self.alert_panel = AlertPanel(self._on_alert_select)
        self.chronicle_panel = ChroniclePanel(self._on_focus_select)
        left_layout.addWidget(self.alert_panel, stretch=5)
        left_layout.addWidget(self.chronicle_panel, stretch=4)
        stage_layout.addWidget(self.left_column, stretch=1)

        self.map_scene = MapScene(session.projections, self._on_select)
        self.map_view = MapView(self.map_scene)
        stage_layout.addWidget(self.map_view, stretch=9)

        bottom_shell = QWidget()
        bottom_layout = QHBoxLayout(bottom_shell)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)

        self.inspector_panel = InspectorPanel(self._on_affordance)
        self.debug_panel = TimelinePanel(title="Debug Trace") if self.session.view_state.debug_mode else None

        self.action_ribbon = ActionRibbon(
            self._step_once,
            self._resume,
            self._pause,
            self._step_batch,
            self._set_map_mode,
            self._select_action,
            self._commit_selected_action,
            self._cycle_overlay,
            self._review_objectives,
        )
        bottom_layout.addWidget(self.action_ribbon, stretch=8)
        bottom_layout.addWidget(self.inspector_panel, stretch=2)
        root_layout.addWidget(bottom_shell, stretch=1)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick_if_running)
        self.timer.start(180)

        self.session.subscribe(self._refresh_from_frame)
        self._last_alerts = ()
        if self.session.current_frame is not None:
            self._refresh_from_frame(self.session.current_frame)

    def _step_once(self) -> None:
        self.time.pause()
        self.session.step_once()

    def _step_batch(self) -> None:
        self.time.pause()
        for _ in range(5):
            self.session.step_once()

    def _pause(self) -> None:
        self.time.pause()
        if self.session.current_frame is not None:
            self._refresh_from_frame(self.session.current_frame)

    def _resume(self) -> None:
        self.time.resume()
        if self.session.current_frame is not None:
            self._refresh_from_frame(self.session.current_frame)

    def _tick_if_running(self) -> None:
        self._animation_tick = (self._animation_tick + 1) % 12
        if self._recent_action_feedback:
            survivors: list[dict[str, object]] = []
            changed = False
            for item in self._recent_action_feedback:
                ttl = int(item["ttl"]) - 1
                if ttl > 0:
                    item["ttl"] = ttl
                    survivors.append(item)
                changed = True
            self._recent_action_feedback = survivors
            if changed and self.session.current_frame is not None:
                self._refresh_from_frame(self.session.current_frame)
        self.map_scene.advance_animation()
        if self.session.view_state.running:
            if self.session.view_state.speed_mode == "burst":
                for _ in range(2):
                    self.session.step_once()
            elif self._animation_tick % 3 == 0:
                self.session.step_once()

    def _set_map_mode(self, map_mode: str) -> None:
        self.overlays.set_map_mode(map_mode)
        if self.session.current_frame is not None:
            self._refresh_from_frame(self.session.current_frame)

    def _cycle_overlay(self) -> None:
        fog_enabled = "fog" in self.session.view_state.active_overlays
        self.overlays.set_enabled("fog", not fog_enabled)
        if self.session.current_frame is not None:
            self._refresh_from_frame(self.session.current_frame)

    def _review_objectives(self) -> None:
        if self.session.world.player_state.active_objectives and self.session.current_frame is not None:
            self._refresh_from_frame(self.session.current_frame)

    def _select_action(self, action_id: str, target_ref: str) -> None:
        self.session.select_action(action_id, target_ref)
        if self.session.current_frame is not None:
            self._refresh_from_frame(self.session.current_frame)

    def _commit_selected_action(self) -> None:
        action_id = self.session.view_state.selected_action_id
        target_ref = self.session.view_state.selected_action_target_ref
        if action_id and target_ref:
            self._recent_action_feedback.insert(0, {"action_id": action_id, "target_ref": target_ref, "ttl": 10})
            self._recent_action_feedback = self._recent_action_feedback[:6]
            self.commands.dispatch(action_id, target_ref)
            if self.session.current_frame is not None:
                self._refresh_from_frame(self.session.current_frame)

    def _on_select(self, ref: str | None) -> None:
        self.selection.select(ref)
        if self.session.current_frame is not None:
            self._refresh_from_frame(self.session.current_frame)

    def _on_focus_select(self, ref: str | None) -> None:
        self.selection.select(ref)
        if ref is not None and self.session.current_frame is not None:
            self._focus_map_on_ref(ref)
            self._refresh_from_frame(self.session.current_frame)

    def _on_alert_select(self, ref: str | None, suggested_mode=None) -> None:
        if isinstance(suggested_mode, str):
            self._set_map_mode(suggested_mode)
        self._on_focus_select(ref)

    def _on_affordance(self, label: str, ref: str) -> None:
        if label in {"Focus on map", "Show on timeline", "Pin to timeline", "Open event chain"}:
            self._focus_map_on_ref(ref)
            return
        entity = self.session.world.entity_by_ref(ref)
        if entity is None:
            return
        target_ref: str | None = None
        if label == "Inspect associated settlement":
            target_ref = getattr(entity, "settlement_id", None) or getattr(entity, "capital_settlement_id", None)
        elif label == "Inspect associated polity":
            target_ref = getattr(entity, "polity_id", None)
        elif label == "Show related settlement":
            target_ref = getattr(entity, "settlement_id", None)
        if target_ref is not None:
            self._on_focus_select(target_ref)

    def _focus_map_on_ref(self, ref: str) -> None:
        frame = self.session.current_frame
        if frame is None:
            return
        tile_ref = self._resolve_tile_ref(ref)
        if tile_ref is None:
            return
        tile = next((item for item in frame.tiles if item.ref == tile_ref), None)
        if tile is not None:
            zoom = 2.0 if ref.startswith("tile:") else 1.5 if ref.startswith(("npc:", "settlement:")) else 1.1
            self.map_view.focus_on_tile(tile.x, tile.y, zoom_level=zoom)

    def _resolve_tile_ref(self, ref: str | None) -> str | None:
        if ref is None:
            return None
        if ref.startswith("tile:"):
            return ref
        entity = self.session.world.entity_by_ref(ref)
        if entity is None:
            return None
        tile_ref = getattr(entity, "location_tile_id", None) or getattr(entity, "core_tile_id", None)
        if tile_ref is not None:
            return tile_ref
        if hasattr(entity, "capital_settlement_id"):
            settlement = self.session.world.entity_by_ref(getattr(entity, "capital_settlement_id"))
            tile_ref = getattr(settlement, "core_tile_id", None)
        if tile_ref is None and hasattr(entity, "participant_polity_ids"):
            for polity_id in getattr(entity, "participant_polity_ids", []):
                polity = self.session.world.entity_by_ref(polity_id)
                settlement = self.session.world.entity_by_ref(getattr(polity, "capital_settlement_id", None)) if polity else None
                tile_ref = getattr(settlement, "core_tile_id", None)
                if tile_ref is not None:
                    break
        return tile_ref

    def _tile_cluster(self, frame, center_ref: str | None, radius: int) -> tuple[str, ...]:
        tile_ref = self._resolve_tile_ref(center_ref)
        if tile_ref is None:
            return ()
        center_tile = next((tile for tile in frame.tiles if tile.ref == tile_ref), None)
        if center_tile is None:
            return ()
        refs: list[str] = []
        for tile in frame.tiles:
            distance = abs(tile.x - center_tile.x) + abs(tile.y - center_tile.y)
            if distance <= radius:
                refs.append(tile.ref)
        return tuple(refs)

    def _preview_tiles(self, frame) -> tuple[str, ...]:
        action_id = self.session.view_state.selected_action_id
        target_ref = self.session.view_state.selected_action_target_ref
        if not action_id or not target_ref:
            return ()
        radius = {
            "bless": 0,
            "resource": 1,
            "rumor": 2,
            "miracle": 2,
        }.get(action_id, 0)
        return self._tile_cluster(frame, target_ref, radius)

    def _response_tiles(self, frame) -> tuple[tuple[str, str], ...]:
        response_tiles: list[tuple[str, str]] = []
        for item in self._recent_action_feedback:
            action_id = str(item["action_id"])
            target_ref = str(item["target_ref"])
            for tile_ref in self._tile_cluster(
                frame,
                target_ref,
                {"bless": 0, "resource": 1, "rumor": 2, "miracle": 2}.get(action_id, 0),
            ):
                response_tiles.append((tile_ref, action_id))
        deduped: dict[str, str] = {}
        for tile_ref, action_id in response_tiles:
            deduped[tile_ref] = action_id
        return tuple(deduped.items())

    def _refresh_from_frame(self, frame) -> None:
        alerts = build_alert_stack(self.session.world, frame)
        self._last_alerts = alerts
        alert_tile_severities = tuple(
            (tile_ref, alert.severity)
            for alert in alerts
            for tile_ref in [self._resolve_tile_ref(alert.target_ref)]
            if tile_ref is not None
        )
        if self.session.view_state.selected_ref is None:
            self.selection.select(pick_default_focus_ref(frame, alerts))
        selected_ref = self.session.view_state.selected_ref or (frame.tiles[0].ref if frame.tiles else None)

        if selected_ref is not None and self.session.world.entity_by_ref(selected_ref) is None and not selected_ref.startswith("tile:"):
            fallback = pick_default_focus_ref(frame, alerts)
            self.selection.select(fallback)
            selected_ref = fallback

        self.top_bar.render(build_top_bar(self.session.world, frame, self.session.view_state))
        self.alert_panel.set_alerts(alerts)
        self.chronicle_panel.set_items(build_chronicle_stream(self.session.world, frame))
        self.chronicle_panel.set_history_groups(build_timeline_groups(self.session.world, frame, historical_scale=True))
        self.action_ribbon.set_mode(self.session.view_state.current_map_mode)
        preview_tile_refs = self._preview_tiles(frame)
        response_effects = self._response_tiles(frame)

        if selected_ref is not None:
            panel = build_inspection_panel(self.session.world, selected_ref, debug_mode=self.session.view_state.debug_mode)
            self.inspector_panel.render_panel(panel)
            options = build_intervention_options(self.session.world, selected_ref)
            if self.session.view_state.selected_action_target_ref != selected_ref:
                default_option = next((option for option in options if option.enabled), None)
                self.session.select_action(
                    default_option.action_id if default_option else None,
                    default_option.target_ref if default_option else selected_ref,
                )
            self.action_ribbon.set_options(
                options,
                self.session.view_state.selected_action_id,
                self.session.view_state.selected_action_target_ref,
            )
        self.map_scene.render_frame(
            self.session.view_state.active_overlays,
            selected_ref,
            self.session.view_state.current_map_mode,
            alerts=alerts,
            alert_tile_severities=alert_tile_severities,
            selected_action_id=self.session.view_state.selected_action_id,
            selected_action_target_ref=self.session.view_state.selected_action_target_ref,
            preview_tile_refs=preview_tile_refs,
            response_effects=response_effects,
        )

        if self.debug_panel is not None:
            self.debug_panel.set_lines(build_debug_lines(self.session.world, frame)[:18])
