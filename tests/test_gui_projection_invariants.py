from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication

from coma_engine.config.schema import default_config
from coma_engine.gui.presentation import build_alert_stack
from coma_engine.gui.render.map_scene import MapScene
from coma_engine.gui.session import GuiSession
from coma_engine.gui.sync.world_projector import WorldProjector
from coma_engine.simulation.phases import _found_polity
from coma_engine.systems.generation import create_world
from coma_engine.systems.propagation import emit_info_packet, propagate_info_packets


class GuiProjectionInvariantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_world_projector_preserves_tile_count_and_step(self) -> None:
        world = create_world(default_config(seed=101))
        frame = WorldProjector().project(world)
        self.assertEqual(frame.time_state.step, world.current_step)
        self.assertEqual(len(frame.tiles), len(world.tiles))
        self.assertEqual(len({tile.ref for tile in frame.tiles}), len(world.tiles))

    def test_info_flow_projection_comes_from_real_packets(self) -> None:
        world = create_world(default_config(seed=102))
        npc_id = next(iter(world.npcs))
        packet_id = emit_info_packet(
            world,
            source_event_id=None,
            origin_actor_id=npc_id,
            content_domain="belief",
            subject_ref="destiny",
            location_ref=world.npcs[npc_id].location_tile_id,
            strength=18.0,
            visibility_scope="local",
            ttl=3,
            truth_alignment=1.0,
            propagation_channels=["spatial"],
        )
        propagate_info_packets(world)
        frame = WorldProjector().project(world)
        self.assertTrue(any(flow.packet_id == packet_id for flow in frame.info_flows))

    def test_gui_session_syncs_after_step_without_parallel_state(self) -> None:
        world = create_world(default_config(seed=103))
        session = GuiSession(world)
        first_frame = session.current_frame
        self.assertIsNotNone(first_frame)
        session.step_once()
        self.assertIs(session.world, world)
        self.assertEqual(session.current_frame.time_state.step, world.current_step)  # type: ignore[union-attr]
        self.assertIsNotNone(session.projections.previous)
        self.assertGreaterEqual(len(session.projections.recent), 2)

    def test_map_scene_renders_alert_driven_visual_signal_layer(self) -> None:
        world = create_world(default_config(seed=104))
        session = GuiSession(world)
        session.step_once()
        frame = session.current_frame
        assert frame is not None
        alerts = build_alert_stack(world, frame)
        scene = MapScene(session.projections, lambda _ref: None)
        scene.render_frame({"terrain", "power", "attention", "signals"}, None, "world", alerts=alerts)
        first_count = len(scene.items())
        scene.advance_animation()
        second_count = len(scene.items())
        self.assertGreater(first_count, len(frame.tiles))
        self.assertGreater(second_count, len(frame.tiles))

    def test_world_projector_exposes_dynamic_hotspots_after_change(self) -> None:
        world = create_world(default_config(seed=105))
        session = GuiSession(world)
        session.step_once()
        session.step_once()
        frame = session.current_frame
        assert frame is not None
        self.assertIsNotNone(session.projections.previous)
        self.assertIsInstance(frame.dynamic_hotspots, tuple)
