from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coma_engine.config.schema import default_config
from coma_engine.gui.presentation import (
    build_alert_stack,
    build_chronicle_stream,
    build_intervention_options,
    build_timeline_groups,
    build_top_bar,
    build_world_status,
    pick_default_focus_ref,
)
from coma_engine.gui.session import GuiSession
from coma_engine.systems.generation import create_world


class GuiGameplayLayerTests(unittest.TestCase):
    def test_alert_stack_derives_from_world_signals(self) -> None:
        world = create_world(default_config(seed=131))
        session = GuiSession(world)
        session.step_once()
        frame = session.current_frame
        assert frame is not None
        alerts = build_alert_stack(world, frame)
        self.assertTrue(alerts)
        self.assertTrue(any(item.target_ref is not None for item in alerts))
        self.assertTrue(all(item.severity in {"critical", "major", "notable"} for item in alerts))

    def test_top_bar_and_default_focus_are_player_facing(self) -> None:
        world = create_world(default_config(seed=132))
        session = GuiSession(world)
        frame = session.current_frame
        assert frame is not None
        alerts = build_alert_stack(world, frame)
        top_bar = build_top_bar(world, frame, session.view_state)
        status = build_world_status(world, frame)
        focus_ref = pick_default_focus_ref(frame, alerts)
        self.assertIn("Step", top_bar.step_label)
        self.assertTrue(top_bar.atmosphere_labels)
        self.assertIn("Hotspots", status.headline)
        self.assertIsNotNone(focus_ref)

    def test_chronicle_and_timeline_compress_world_change(self) -> None:
        world = create_world(default_config(seed=133))
        session = GuiSession(world)
        session.step_once()
        frame = session.current_frame
        assert frame is not None
        chronicle = build_chronicle_stream(world, frame)
        groups = build_timeline_groups(world, frame)
        self.assertTrue(chronicle)
        self.assertTrue(groups)
        self.assertTrue(all(group.title in {"Major Shifts", "Regional Chronicle", "Signals And Rumors"} for group in groups))

    def test_intervention_cards_use_player_language_and_preview(self) -> None:
        world = create_world(default_config(seed=134))
        settlement_ref = next(iter(world.settlements))
        options = build_intervention_options(world, settlement_ref)
        self.assertTrue(any(option.label == "Bless Harvest" for option in options))
        self.assertTrue(any(option.preview_lines for option in options if option.action_id == "resource"))
