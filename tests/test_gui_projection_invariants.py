from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coma_engine.config.schema import default_config
from coma_engine.gui.session import GuiSession
from coma_engine.gui.sync.world_projector import WorldProjector
from coma_engine.simulation.phases import _found_polity
from coma_engine.systems.generation import create_world
from coma_engine.systems.propagation import emit_info_packet, propagate_info_packets


class GuiProjectionInvariantTests(unittest.TestCase):
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
