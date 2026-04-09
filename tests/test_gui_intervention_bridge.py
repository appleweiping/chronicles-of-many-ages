from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coma_engine.config.schema import default_config
from coma_engine.gui.interaction.intervention_controller import InterventionController
from coma_engine.gui.presentation.intervention_presenter import build_intervention_options
from coma_engine.gui.session import GuiSession
from coma_engine.systems.generation import create_world


class GuiInterventionBridgeTests(unittest.TestCase):
    def test_intervention_options_follow_target_type(self) -> None:
        options = build_intervention_options("tile:1")
        self.assertTrue(any(option.action_id == "rumor" and option.enabled for option in options))
        self.assertTrue(any(option.action_id == "miracle" and option.enabled for option in options))

    def test_intervention_controller_only_queues_formal_effects(self) -> None:
        world = create_world(default_config(seed=121))
        session = GuiSession(world)
        controller = InterventionController(session)
        npc_id = next(iter(world.npcs))
        before_health = world.npcs[npc_id].health
        controller.bless_npc(npc_id)
        self.assertEqual(world.npcs[npc_id].health, before_health)
        self.assertTrue(world.delayed_effect_queue)
        self.assertEqual(world.delayed_effect_queue[-1]["channel"], "modifier")
