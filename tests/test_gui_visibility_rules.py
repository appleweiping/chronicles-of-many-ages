from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coma_engine.config.schema import default_config
from coma_engine.gui.presentation.entity_panels import build_inspection_panel
from coma_engine.gui.presentation.visibility import visibility_for_ref
from coma_engine.simulation.phases import _found_polity, run_event_phase
from coma_engine.systems.generation import create_world


class GuiVisibilityRuleTests(unittest.TestCase):
    def test_unknown_polity_panel_remains_rumored(self) -> None:
        world = create_world(default_config(seed=111))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        _found_polity(world, leader.id, leader.settlement_id)
        polity_id = next(iter(world.polities))
        run_event_phase(world.clone_for_phase(), world)
        world.player_state.known_entities.discard(polity_id)
        panel = build_inspection_panel(world, polity_id, debug_mode=False)
        lines = [field.value for section in panel.sections for field in section.fields]
        self.assertTrue(any("visibility=rumored" in line for line in lines))

    def test_known_settlement_visibility_is_confirmed(self) -> None:
        world = create_world(default_config(seed=112))
        settlement_id = next(iter(world.settlements))
        world.player_state.known_entities.add(settlement_id)
        self.assertEqual(visibility_for_ref(world, settlement_id), "confirmed")
