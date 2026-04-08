from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coma_engine.config.schema import default_config
from coma_engine.actions.models import Action
from coma_engine.core.transfers import move_npc_to_tile, reconcile_references, validate_reference_consistency
from coma_engine.explain import debug_grade_action_explanations
from coma_engine.player.interventions import queue_information_intervention, queue_npc_modifier_intervention
from coma_engine.simulation.engine import SimulationEngine
from coma_engine.simulation.phases import _found_polity, run_political_phase, run_resolution_phase
from coma_engine.systems.generation import create_world
from coma_engine.systems.propagation import emit_command_packet


class CoreInvariantTests(unittest.TestCase):
    def test_seed_replay_is_deterministic(self) -> None:
        world_a = create_world(default_config(seed=11))
        world_b = create_world(default_config(seed=11))
        engine_a = SimulationEngine(world_a)
        engine_b = SimulationEngine(world_b)
        for _ in range(6):
            engine_a.step()
            engine_b.step()
        summary_a = [(event.event_type, event.timestamp_step) for event in world_a.events.values()]
        summary_b = [(event.event_type, event.timestamp_step) for event in world_b.events.values()]
        self.assertEqual(summary_a, summary_b)
        self.assertEqual(sorted(world_a.polities), sorted(world_b.polities))

    def test_transfer_interface_keeps_mirrors_consistent(self) -> None:
        world = create_world(default_config(seed=3))
        npc_id = next(iter(world.npcs))
        npc = world.npcs[npc_id]
        old_tile_id = npc.location_tile_id
        new_tile_id = next(tile_id for tile_id in world.tiles if tile_id != old_tile_id)
        move_npc_to_tile(world, npc_id, new_tile_id)
        reconcile_references(world)
        self.assertFalse(validate_reference_consistency(world))
        self.assertNotIn(npc_id, world.tiles[old_tile_id].resident_npc_ids)
        self.assertIn(npc_id, world.tiles[new_tile_id].resident_npc_ids)

    def test_low_rank_npc_does_not_frequently_enter_high_politics(self) -> None:
        world = create_world(default_config(seed=13))
        SimulationEngine(world).step()
        low_rank_npcs = [npc for npc in world.npcs.values() if npc.office_rank < 3]
        for npc in low_rank_npcs:
            self.assertNotIn("FOUND_POLITY", npc.candidate_actions)
            self.assertNotIn("DECLARE_WAR", npc.candidate_actions)

    def test_found_polity_requires_thresholds(self) -> None:
        world = create_world(default_config(seed=5))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        settlement = world.settlements[leader.settlement_id]
        settlement.stability = 10.0
        world.factions[leader.faction_id].support_score = 20.0
        SimulationEngine(world).step()
        self.assertFalse(world.polities)

    def test_phase_snapshots_and_debug_explanations_exist(self) -> None:
        world = create_world(default_config(seed=17))
        SimulationEngine(world).step()
        self.assertIn("DecisionPhase", world.phase_snapshot_buffer)
        explanations = debug_grade_action_explanations(world, 0)
        self.assertTrue(isinstance(explanations, dict))

    def test_player_interventions_enter_via_formal_channels(self) -> None:
        world = create_world(default_config(seed=19))
        npc_id = next(iter(world.npcs))
        queue_npc_modifier_intervention(
            world,
            npc_id,
            modifier_type="blessing",
            domain="yield.food",
            magnitude=1.0,
            duration=2,
        )
        queue_information_intervention(
            world,
            content_domain="belief",
            subject_ref=npc_id,
            location_ref=world.npcs[npc_id].location_tile_id,
            strength=20.0,
        )
        SimulationEngine(world).step()
        self.assertTrue(world.modifiers)
        self.assertTrue(world.info_packets)

    def test_archived_settlement_remains_resolvable(self) -> None:
        world = create_world(default_config(seed=23))
        settlement_id = next(iter(world.settlements))
        settlement = world.settlements[settlement_id]
        for npc_id in list(settlement.resident_npc_ids):
            world.npcs[npc_id].alive = False
        SimulationEngine(world).step()
        self.assertIn(settlement_id, world.archived_settlements)
        self.assertIsNotNone(world.entity_by_ref(settlement_id))

    def test_command_packet_drives_tax_execution(self) -> None:
        world = create_world(default_config(seed=29))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        _found_polity(world, leader.id, leader.settlement_id)
        polity = next(iter(world.polities.values()))
        settlement = world.settlements[leader.settlement_id]
        settlement.stored_resources["wealth"] = 30.0
        settlement.current_taxable_output = 20.0
        initial = polity.treasury["wealth"]
        packet_id = emit_command_packet(world, leader.id, settlement.id, "formal_tax_order")
        world.history_index["packet_deliveries"][packet_id] = [leader.id]
        run_political_phase(world.clone_for_phase(), world)
        self.assertGreater(polity.treasury["wealth"], initial)

    def test_continuous_action_can_be_interrupted_with_formal_record(self) -> None:
        world = create_world(default_config(seed=31))
        actor = next(iter(world.npcs.values()))
        start_tile = next(
            tile.id
            for tile in world.tiles.values()
            if tile.terrain_type != "water"
            and any(world.tiles[adjacent_id].terrain_type != "water" for adjacent_id in tile.adjacent_tile_ids)
        )
        move_npc_to_tile(world, actor.id, start_tile)
        target_tile = next(
            tile_id
            for tile_id in world.tiles[start_tile].adjacent_tile_ids
            if world.tiles[tile_id].terrain_type != "water"
        )
        world.tiles[target_tile].danger = 95.0
        world.action_queue.append(
            Action(
                id=world.next_id("action"),
                action_type="MOVE",
                actor_id=actor.id,
                target_npc_id=None,
                target_tile_id=target_tile,
                target_settlement_id=None,
                target_faction_id=None,
                target_polity_id=None,
                declared_step=world.current_step,
                priority_class="survival",
                duration_type="travel",
                estimated_duration=2,
                resource_cost={"food": 0.2, "wood": 0.0, "ore": 0.0, "wealth": 0.0},
                risk_value=10.0,
                availability_rule_id="movement",
                resolution_group_key=f"MOVE:{target_tile}",
                status="declared",
            )
        )
        run_resolution_phase(world.clone_for_phase(), world)
        self.assertTrue(any(outcome.result == "interrupted" for outcome in world.outcome_records))

    def test_command_chain_can_delay_when_local_executor_is_missing(self) -> None:
        world = create_world(default_config(seed=37))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        _found_polity(world, leader.id, leader.settlement_id)
        settlement = world.settlements[leader.settlement_id]
        packet_id = emit_command_packet(world, leader.id, settlement.id, "formal_tax_order")
        world.history_index["packet_deliveries"][packet_id] = []
        run_political_phase(world.clone_for_phase(), world)
        self.assertTrue(
            any(entry["outcome"] == "delayed_no_executor" for entry in world.history_index["command_execution_log"])
        )


if __name__ == "__main__":
    unittest.main()
