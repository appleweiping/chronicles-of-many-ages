from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coma_engine.config.schema import default_config
from coma_engine.actions.models import Action
from coma_engine.core.transfers import (
    assign_npc_faction,
    assign_npc_settlement,
    assign_settlement_faction,
    assign_settlement_tiles,
    move_npc_to_tile,
    reconcile_references,
    validate_reference_consistency,
)
from coma_engine.explain import debug_grade_action_explanations, player_grade_npc_summary
from coma_engine.models.entities import Faction, Settlement
from coma_engine.player.interventions import queue_information_intervention, queue_npc_modifier_intervention
from coma_engine.simulation.engine import SimulationEngine
from coma_engine.simulation.phases import _declare_war, _found_polity, run_political_phase, run_resolution_phase, run_resource_phase
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

    def test_children_do_not_count_as_full_labor_pool(self) -> None:
        world = create_world(default_config(seed=41))
        settlement = next(iter(world.settlements.values()))
        resident_ids = list(settlement.resident_npc_ids)
        if len(resident_ids) < 3:
            needed = 3 - len(resident_ids)
            reinforcements = [npc.id for npc in world.npcs.values() if npc.id not in resident_ids][:needed]
            for npc_id in reinforcements:
                move_npc_to_tile(world, npc_id, settlement.core_tile_id)
                assign_npc_settlement(world, npc_id, settlement.id)
            resident_ids = list(settlement.resident_npc_ids)[:3]
        world.npcs[resident_ids[0]].age = 10.0
        world.npcs[resident_ids[1]].age = 25.0
        world.npcs[resident_ids[2]].age = 68.0
        run_resource_phase(world.clone_for_phase(), world)
        self.assertEqual(settlement.labor_pool, 1.0)

    def test_war_strain_reduces_civil_legitimacy_and_consumes_treasury(self) -> None:
        world = create_world(default_config(seed=43))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        _found_polity(world, leader.id, leader.settlement_id)
        first_polity_id = next(iter(world.polities))
        source_residents = [
            npc.id
            for npc in world.npcs.values()
            if npc.settlement_id != leader.settlement_id and npc.id != leader.id
        ][:3]
        target_tile = next(
            tile.id
            for tile in world.tiles.values()
            if tile.terrain_type == "plains" and tile.settlement_id is None
        )
        second_settlement_id = world.next_id("settlement")
        world.settlements[second_settlement_id] = Settlement(
            id=second_settlement_id,
            name="Rival Camp",
            core_tile_id=target_tile,
            member_tile_ids=[target_tile],
            resident_npc_ids=[],
            stored_resources={"food": 12.0, "wood": 5.0, "ore": 1.0, "wealth": 4.0},
            security_level=48.0,
            stability=56.0,
            faction_id=None,
            polity_id=None,
            active_modifier_ids=[],
            labor_pool=3.0,
        )
        assign_settlement_tiles(world, second_settlement_id, [target_tile])
        for npc_id in source_residents:
            move_npc_to_tile(world, npc_id, target_tile)
            assign_npc_settlement(world, npc_id, second_settlement_id)
        rival_faction_id = world.next_id("faction")
        world.factions[rival_faction_id] = Faction(
            id=rival_faction_id,
            name="Rival Circle",
            leader_npc_id=source_residents[0],
            member_npc_ids=[],
            settlement_ids=[],
            support_score=72.0,
            cohesion=70.0,
            agenda_type="survival",
            legitimacy_seed_components={"support": 72.0},
            active_modifier_ids=[],
        )
        for npc_id in source_residents:
            assign_npc_faction(world, npc_id, rival_faction_id)
        assign_settlement_faction(world, second_settlement_id, rival_faction_id)
        rival_leader = world.npcs[source_residents[0]]
        rival_leader.office_rank = 4
        _found_polity(world, rival_leader.id, second_settlement_id)
        polity_ids = list(world.polities)
        self.assertEqual(len(polity_ids), 2)
        _declare_war(world, polity_ids[0], polity_ids[1])
        before = {polity_id: world.polities[polity_id].treasury["food"] for polity_id in polity_ids}
        run_political_phase(world.clone_for_phase(), world)
        for polity_id in polity_ids:
            polity = world.polities[polity_id]
            self.assertGreater(polity.legitimacy_components.get("war_strain", 0.0), 0.0)
            self.assertLessEqual(polity.treasury["food"], before[polity_id])

    def test_player_grade_npc_summary_hides_raw_needs_dict(self) -> None:
        world = create_world(default_config(seed=47))
        npc_id = next(iter(world.npcs))
        lines = player_grade_npc_summary(world, npc_id)
        self.assertTrue(all("{" not in line for line in lines))


if __name__ == "__main__":
    unittest.main()
