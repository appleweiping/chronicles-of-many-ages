from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow, QSplitter, QTabWidget, QVBoxLayout, QWidget

from coma_engine.gui.interaction import (
    CameraController,
    CommandRouter,
    InterventionController,
    OverlayController,
    SelectionController,
    TimeController,
)
from coma_engine.gui.presentation import (
    build_debug_lines,
    build_inspection_panel,
    build_intervention_options,
    build_player_history,
)
from coma_engine.gui.render.map_scene import MapScene
from coma_engine.gui.render.map_view import MapView
from coma_engine.gui.render.panels.control_panel import ControlPanel
from coma_engine.gui.render.panels.inspector_panel import InspectorPanel
from coma_engine.gui.render.panels.intervention_panel import InterventionPanel
from coma_engine.gui.render.panels.overlay_panel import OverlayPanel
from coma_engine.gui.render.panels.status_panel import StatusPanel
from coma_engine.gui.render.panels.timeline_panel import TimelinePanel
from coma_engine.gui.render.widgets.legend_widget import LegendWidget
from coma_engine.gui.render.widgets.phase_strip import PhaseStrip
from coma_engine.gui.session import GuiSession


class MainWindow(QMainWindow):
    def __init__(self, session: GuiSession):
        super().__init__()
        self.session = session
        self.setWindowTitle("Chronicles of Many Ages")
        self.resize(1440, 900)

        self.selection = SelectionController(session)
        self.camera = CameraController(session)
        self.time = TimeController(session)
        self.overlays = OverlayController(session)
        self.interventions = InterventionController(session)
        self.commands = CommandRouter(self.interventions)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        self.setCentralWidget(root)

        self.phase_strip = PhaseStrip()
        self.status_panel = StatusPanel()
        self.control_panel = ControlPanel(self._step_once, self._pause, self._resume)
        root_layout.addWidget(self.phase_strip)
        root_layout.addWidget(self.control_panel)
        root_layout.addWidget(self.status_panel)

        splitter = QSplitter()
        root_layout.addWidget(splitter, stretch=1)

        self.map_scene = MapScene(session.projections, self._on_select)
        self.map_view = MapView(self.map_scene)
        splitter.addWidget(self.map_view)

        side_tabs = QTabWidget()
        splitter.addWidget(side_tabs)

        inspector_page = QWidget()
        inspector_layout = QVBoxLayout(inspector_page)
        self.inspector_panel = InspectorPanel()
        self.intervention_panel = InterventionPanel(self._dispatch_action)
        inspector_layout.addWidget(self.inspector_panel)
        inspector_layout.addWidget(self.intervention_panel)
        side_tabs.addTab(inspector_page, "Inspect")

        timeline_page = QWidget()
        timeline_layout = QVBoxLayout(timeline_page)
        self.timeline_panel = TimelinePanel()
        self.debug_panel = TimelinePanel()
        timeline_layout.addWidget(self.timeline_panel)
        timeline_layout.addWidget(self.debug_panel)
        side_tabs.addTab(timeline_page, "History")

        overlay_page = QWidget()
        overlay_layout = QVBoxLayout(overlay_page)
        overlay_layout.addWidget(OverlayPanel(self._toggle_overlay, set(self.session.view_state.active_overlays)))
        overlay_layout.addWidget(LegendWidget())
        side_tabs.addTab(overlay_page, "Overlays")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick_if_running)
        self.timer.start(400)

        self.session.subscribe(self._refresh_from_frame)
        if self.session.current_frame is not None:
            self._refresh_from_frame(self.session.current_frame)

    def _step_once(self) -> None:
        self.time.pause()
        self.session.step_once()

    def _pause(self) -> None:
        self.time.pause()

    def _resume(self) -> None:
        self.time.resume()

    def _tick_if_running(self) -> None:
        if self.session.view_state.running:
            self.session.step_once()

    def _toggle_overlay(self, overlay_name: str, enabled: bool) -> None:
        self.overlays.set_enabled(overlay_name, enabled)
        if self.session.current_frame is not None:
            self.map_scene.render_frame(self.session.view_state.active_overlays, self.session.view_state.selected_ref)

    def _on_select(self, ref: str | None) -> None:
        self.selection.select(ref)
        if self.session.current_frame is not None:
            self._refresh_from_frame(self.session.current_frame)

    def _dispatch_action(self, action_id: str, target_ref: str) -> None:
        self.commands.dispatch(action_id, target_ref)
        if self.session.current_frame is not None:
            self._refresh_from_frame(self.session.current_frame)

    def _refresh_from_frame(self, frame) -> None:
        self.phase_strip.set_time_state(frame.time_state)
        self.status_panel.update_from_frame(frame, self.session.view_state.selected_ref)
        self.map_scene.render_frame(self.session.view_state.active_overlays, self.session.view_state.selected_ref)

        selected_ref = self.session.view_state.selected_ref or (frame.tiles[0].ref if frame.tiles else None)
        if selected_ref is not None:
            panel = build_inspection_panel(self.session.world, selected_ref, debug_mode=self.session.view_state.debug_mode)
            self.inspector_panel.render_panel(panel)
            self.intervention_panel.set_options(build_intervention_options(selected_ref))

        self.timeline_panel.set_lines(build_player_history(self.session.world, frame))
        self.debug_panel.set_lines(build_debug_lines(self.session.world, frame)[:18])
