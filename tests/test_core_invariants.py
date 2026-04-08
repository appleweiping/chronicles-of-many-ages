from __future__ import annotations

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from coma_engine.config.schema import default_config
from coma_engine.actions.models import Action
from coma_engine.core.transfers import (
    assign_npc_faction,
    assign_npc_polity,
    assign_npc_settlement,
    assign_settlement_faction,
    assign_settlement_polity,
    assign_settlement_tiles,
    move_npc_to_tile,
    reconcile_references,
    validate_reference_consistency,
)
from coma_engine.explain import (
    debug_grade_action_explanations,
    debug_grade_step_report,
    player_grade_known_entities,
    player_grade_npc_summary,
    player_grade_polity_summary,
    player_grade_polity_recent_factors,
    player_grade_settlement_summary,
    player_grade_settlement_recent_factors,
    player_grade_war_recent_factors,
    player_grade_war_summary,
)
from coma_engine.models.entities import Event, Faction, MemoryEntry, RelationEntry, Settlement
from coma_engine.player.interventions import queue_information_intervention, queue_npc_modifier_intervention
from coma_engine.simulation.engine import SimulationEngine
from coma_engine.simulation.phases import _declare_war, _found_polity, run_event_phase, run_political_phase, run_resolution_phase, run_resource_phase
from coma_engine.systems.generation import create_world
from coma_engine.systems.propagation import emit_command_packet, emit_info_packet, propagate_info_packets


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

    def test_command_chain_can_translate_into_skimming(self) -> None:
        world = create_world(default_config(seed=39))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        _found_polity(world, leader.id, leader.settlement_id)
        polity_id = next(iter(world.polities))
        target_settlement_id = leader.settlement_id
        target_settlement = world.settlements[target_settlement_id]
        target_settlement.stored_resources = {"food": 10.0, "wood": 4.0, "ore": 1.0, "wealth": 16.0}
        target_settlement.stability = 46.0
        local_executor_id = next(npc_id for npc_id in target_settlement.resident_npc_ids if npc_id != leader.id)
        assign_npc_faction(world, local_executor_id, None)
        world.npcs[local_executor_id].office_rank = 1
        world.npcs[local_executor_id].relationships[leader.id] = RelationEntry(
            trust=6.0, fear=10.0, grievance=34.0, familiarity=10.0
        )
        before_treasury = world.polities[polity_id].treasury["wealth"]
        packet_id = emit_command_packet(world, leader.id, target_settlement_id, "formal_tax_order")
        world.history_index["packet_deliveries"][packet_id] = [local_executor_id]
        run_political_phase(world.clone_for_phase(), world)
        self.assertTrue(any(entry["mode"] == "skim" for entry in world.history_index["local_command_log"]))
        self.assertGreater(world.polities[polity_id].treasury["wealth"], before_treasury)
        self.assertTrue(
            any(
                entry["flow_type"] == "tax_command" and entry["retained_value"] > 0.0
                for entry in world.history_index["resource_flow_log"]
            )
        )
        self.assertTrue(
            any(entry["kind"] == "skimming" for entry in world.history_index["command_consequence_log"])
        )

    def test_allocate_resources_action_moves_treasury_to_settlement(self) -> None:
        world = create_world(default_config(seed=40))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        _found_polity(world, leader.id, leader.settlement_id)
        polity_id = next(iter(world.polities))
        polity = world.polities[polity_id]
        settlement = world.settlements[leader.settlement_id]
        local_executor_id = next(npc_id for npc_id in settlement.resident_npc_ids if npc_id != leader.id)
        polity.treasury.update({"food": 14.0, "wood": 6.0, "ore": 3.0, "wealth": 2.0})
        settlement.stored_resources.update({"food": 2.0, "wood": 0.5, "ore": 0.0, "wealth": 0.0})
        world.action_queue.append(
            Action(
                id=world.next_id("action"),
                action_type="ALLOCATE_RESOURCES",
                actor_id=leader.id,
                target_npc_id=None,
                target_tile_id=None,
                target_settlement_id=settlement.id,
                target_faction_id=None,
                target_polity_id=None,
                declared_step=world.current_step,
                priority_class="civic",
                duration_type="instant",
                estimated_duration=1,
                resource_cost={"food": 0.0, "wood": 0.0, "ore": 0.0, "wealth": 0.0},
                risk_value=0.0,
                availability_rule_id="allocate_resources",
                resolution_group_key=f"ALLOCATE_RESOURCES:{settlement.id}",
                status="declared",
            )
        )
        before_food = settlement.stored_resources["food"]
        before_treasury_food = polity.treasury["food"]
        run_resolution_phase(world.clone_for_phase(), world)
        packet_id = next(
            packet.id
            for packet in world.info_packets
            if packet.content_domain == "command" and world.history_index["command_packet_subjects"].get(packet.id) == "resource_allocation"
        )
        world.history_index["packet_deliveries"][packet_id] = [local_executor_id]
        run_political_phase(world.clone_for_phase(), world)
        self.assertGreater(settlement.stored_resources["food"], before_food)
        self.assertLess(polity.treasury["food"], before_treasury_food)
        self.assertTrue(
            any(entry["flow_type"] == "resource_allocation" for entry in world.history_index["resource_flow_log"])
        )

    def test_resource_allocation_skimming_can_divert_to_executor_inventory(self) -> None:
        world = create_world(default_config(seed=41))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        _found_polity(world, leader.id, leader.settlement_id)
        polity = next(iter(world.polities.values()))
        settlement = world.settlements[leader.settlement_id]
        local_executor_id = next(npc_id for npc_id in settlement.resident_npc_ids if npc_id != leader.id)
        assign_npc_faction(world, local_executor_id, None)
        world.npcs[local_executor_id].office_rank = 1
        world.npcs[local_executor_id].relationships[leader.id] = RelationEntry(
            trust=6.0, fear=10.0, grievance=34.0, familiarity=10.0
        )
        polity.treasury.update({"food": 14.0, "wood": 6.0, "ore": 3.0, "wealth": 2.0})
        settlement.stored_resources.update({"food": 2.0, "wood": 0.5, "ore": 0.0, "wealth": 0.0})
        before_inventory_food = world.npcs[local_executor_id].personal_inventory.get("food", 0.0)
        packet_id = emit_command_packet(world, leader.id, settlement.id, "resource_allocation")
        world.history_index["packet_deliveries"][packet_id] = [local_executor_id]
        run_political_phase(world.clone_for_phase(), world)
        self.assertGreater(world.npcs[local_executor_id].personal_inventory.get("food", 0.0), before_inventory_food)
        self.assertTrue(
            any(entry["kind"] == "allocation_diverted" for entry in world.history_index["command_consequence_log"])
        )
        self.assertTrue(
            any(
                entry["flow_type"] == "resource_allocation" and entry["diverted_value"] > 0.0
                for entry in world.history_index["resource_flow_log"]
            )
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

    def test_war_supply_draws_from_local_settlements_and_updates_support(self) -> None:
        world = create_world(default_config(seed=44))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        _found_polity(world, leader.id, leader.settlement_id)
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
            name="Supply Camp",
            core_tile_id=target_tile,
            member_tile_ids=[target_tile],
            resident_npc_ids=[],
            stored_resources={"food": 18.0, "wood": 8.0, "ore": 3.0, "wealth": 4.0},
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
            name="Supply Ring",
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
        for polity_id in polity_ids:
            polity = world.polities[polity_id]
            polity.treasury.update({"food": 6.0, "wood": 3.0, "ore": 1.5, "wealth": 2.0})
            for settlement_id in polity.member_settlement_ids:
                world.settlements[settlement_id].stored_resources["food"] += 8.0
                world.settlements[settlement_id].stored_resources["wood"] += 4.0
                world.settlements[settlement_id].stored_resources["ore"] += 2.0
        _declare_war(world, polity_ids[0], polity_ids[1])
        war_id = next(iter(world.war_states))
        before_food = {
            settlement_id: world.settlements[settlement_id].stored_resources["food"]
            for settlement_id in world.settlements
        }
        before_support = dict(world.war_states[war_id].war_support_levels)
        run_political_phase(world.clone_for_phase(), world)
        self.assertTrue(world.history_index["war_supply_log"])
        self.assertTrue(
            any(entry["flow_type"] == "war_supply_draw" for entry in world.history_index["resource_flow_log"])
        )
        self.assertTrue(
            any(entry["flow_type"] == "war_supply_result" for entry in world.history_index["resource_flow_log"])
        )
        self.assertTrue(
            any(
                world.settlements[settlement_id].stored_resources["food"] < before_food[settlement_id]
                for settlement_id in before_food
            )
        )
        self.assertNotEqual(before_support, world.war_states[war_id].war_support_levels)

    def test_muster_force_feeds_war_support_and_local_burden(self) -> None:
        world = create_world(default_config(seed=44))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        _found_polity(world, leader.id, leader.settlement_id)
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
            name="Rival Muster Camp",
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
            name="Rival Muster Ring",
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
        _declare_war(world, polity_ids[0], polity_ids[1])
        war_id = next(iter(world.war_states))
        settlement = world.settlements[leader.settlement_id]
        resident_id = next(npc_id for npc_id in settlement.resident_npc_ids if npc_id != leader.id)
        before_support = world.war_states[war_id].war_support_levels[polity_ids[0]]
        before_stability = settlement.stability
        packet_id = emit_command_packet(world, leader.id, settlement.id, "muster_force")
        world.history_index["packet_deliveries"][packet_id] = [resident_id]
        run_political_phase(world.clone_for_phase(), world)
        self.assertGreater(world.war_states[war_id].war_support_levels[polity_ids[0]], before_support)
        self.assertLess(settlement.stability, before_stability)
        self.assertTrue(world.history_index["war_command_log"])
        self.assertTrue(
            any(entry["kind"] == "war_mobilized" for entry in world.history_index["command_consequence_log"])
        )

    def test_war_loot_first_enters_settlement_then_partially_remits(self) -> None:
        world = create_world(default_config(seed=45))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        _found_polity(world, leader.id, leader.settlement_id)
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
            name="Rival Port",
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
            name="Harbor Circle",
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
        _declare_war(world, polity_ids[0], polity_ids[1])
        winner_capital_id = world.polities[polity_ids[0]].capital_settlement_id
        before_local = world.settlements[winner_capital_id].stored_resources["wealth"]
        run_political_phase(world.clone_for_phase(), world)
        self.assertTrue(world.history_index["loot_remittance_log"])
        self.assertTrue(
            any(entry["flow_type"] == "war_loot_capture" for entry in world.history_index["resource_flow_log"])
        )
        self.assertTrue(
            any(entry["flow_type"] == "war_loot_remittance" for entry in world.history_index["resource_flow_log"])
        )
        self.assertGreaterEqual(world.settlements[winner_capital_id].stored_resources["wealth"], before_local)

    def test_player_grade_npc_summary_hides_raw_needs_dict(self) -> None:
        world = create_world(default_config(seed=47))
        npc_id = next(iter(world.npcs))
        lines = player_grade_npc_summary(world, npc_id)
        self.assertTrue(all("{" not in line for line in lines))

    def test_trade_success_applies_relation_template(self) -> None:
        world = create_world(default_config(seed=53))
        source_settlement = next(iter(world.settlements.values()))
        actor_id = source_settlement.resident_npc_ids[0]
        target_tile_id = next(
            tile_id
            for tile_id in world.tiles[source_settlement.core_tile_id].adjacent_tile_ids
            if world.tiles[tile_id].terrain_type != "water" and world.tiles[tile_id].settlement_id is None
        )
        target_settlement_id = world.next_id("settlement")
        target_resident_id = next(
            npc.id for npc in world.npcs.values() if npc.id not in source_settlement.resident_npc_ids
        )
        world.settlements[target_settlement_id] = Settlement(
            id=target_settlement_id,
            name="Trade Camp",
            core_tile_id=target_tile_id,
            member_tile_ids=[target_tile_id],
            resident_npc_ids=[],
            stored_resources={"food": 8.0, "wood": 2.0, "ore": 0.0, "wealth": 1.0},
            security_level=40.0,
            stability=52.0,
            faction_id=None,
            polity_id=None,
            active_modifier_ids=[],
            labor_pool=1.0,
        )
        assign_settlement_tiles(world, target_settlement_id, [target_tile_id])
        move_npc_to_tile(world, target_resident_id, target_tile_id)
        assign_npc_settlement(world, target_resident_id, target_settlement_id)
        initial_trust = world.npcs[actor_id].relationships.get(target_resident_id)
        initial_value = initial_trust.trust if initial_trust else 0.0
        world.action_queue.append(
            Action(
                id=world.next_id("action"),
                action_type="TRADE",
                actor_id=actor_id,
                target_npc_id=None,
                target_tile_id=None,
                target_settlement_id=target_settlement_id,
                target_faction_id=None,
                target_polity_id=None,
                declared_step=world.current_step,
                priority_class="civic",
                duration_type="travel",
                estimated_duration=1,
                resource_cost={"food": 0.4, "wood": 0.0, "ore": 0.0, "wealth": 0.2},
                risk_value=0.0,
                availability_rule_id="trade",
                resolution_group_key=f"TRADE:{target_settlement_id}",
                status="declared",
            )
        )
        run_resolution_phase(world.clone_for_phase(), world)
        self.assertGreater(world.npcs[actor_id].relationships[target_resident_id].trust, initial_value)

    def test_memory_conversion_emits_belief_packet(self) -> None:
        world = create_world(default_config(seed=59))
        npc_id = next(iter(world.npcs))
        event_id = world.next_id("event")
        world.events[event_id] = Event(
            id=event_id,
            event_type="PLAYER_MIRACLE",
            timestamp_step=world.current_step,
            location_tile_id=world.npcs[npc_id].location_tile_id,
            region_ref=None,
            participant_ids=[npc_id],
            cause_refs=["test"],
            outcome_summary_code="miracle",
            importance=80.0,
            visibility_scope="local",
            derived_memory_ids=[],
            derived_modifier_ids=[],
            derived_info_packet_ids=[],
        )
        memory_id = world.next_id("memory")
        world.memories[memory_id] = MemoryEntry(
            id=memory_id,
            npc_id=npc_id,
            source_event_id=event_id,
            impression_strength=80.0,
            emotion_tag="salient",
            decay_rate=0.1,
            bias_conversion_rule="default",
            created_step=world.current_step,
            current_effect_weight=10.0,
            is_conversion_ready=True,
        )
        run_event_phase(world.clone_for_phase(), world)
        self.assertTrue(any(packet.content_domain == "belief" for packet in world.info_packets))
        self.assertTrue(world.history_index["memory_conversion_log"])

    def test_suppress_unrest_executes_counteraction_with_relation_cost(self) -> None:
        world = create_world(default_config(seed=61))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        _found_polity(world, leader.id, leader.settlement_id)
        settlement = world.settlements[leader.settlement_id]
        resident_id = next(npc_id for npc_id in settlement.resident_npc_ids if npc_id != leader.id)
        settlement.security_level = 20.0
        packet_id = emit_command_packet(world, leader.id, settlement.id, "suppress_unrest")
        world.history_index["packet_deliveries"][packet_id] = [resident_id]
        before_security = settlement.security_level
        run_political_phase(world.clone_for_phase(), world)
        relation = world.npcs[resident_id].relationships[leader.id]
        self.assertGreater(settlement.security_level, before_security)
        self.assertGreater(relation.fear, 0.0)
        self.assertGreater(relation.grievance, 0.0)

    def test_debug_and_player_views_surface_resource_chain(self) -> None:
        world = create_world(default_config(seed=63))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        _found_polity(world, leader.id, leader.settlement_id)
        polity_id = next(iter(world.polities))
        settlement = world.settlements[leader.settlement_id]
        settlement.stored_resources = {"food": 10.0, "wood": 4.0, "ore": 1.0, "wealth": 16.0}
        settlement.stability = 46.0
        local_executor_id = next(npc_id for npc_id in settlement.resident_npc_ids if npc_id != leader.id)
        assign_npc_faction(world, local_executor_id, None)
        world.npcs[local_executor_id].office_rank = 1
        world.npcs[local_executor_id].relationships[leader.id] = RelationEntry(
            trust=6.0, fear=10.0, grievance=34.0, familiarity=10.0
        )
        packet_id = emit_command_packet(world, leader.id, settlement.id, "formal_tax_order")
        world.history_index["packet_deliveries"][packet_id] = [local_executor_id]
        run_political_phase(world.clone_for_phase(), world)
        debug_lines = debug_grade_step_report(world, world.current_step)
        settlement_lines = player_grade_settlement_summary(world, settlement.id)
        polity_lines = player_grade_polity_summary(world, polity_id)
        self.assertTrue(any(line.startswith("resource_flow:") for line in debug_lines))
        self.assertTrue(any(line.startswith("command_effect:") for line in debug_lines))
        self.assertTrue(any("taxable_output=" in line for line in settlement_lines))
        self.assertTrue(any("network_integrity=" in line for line in polity_lines))

    def test_debug_view_surfaces_war_command_chain(self) -> None:
        world = create_world(default_config(seed=64))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        _found_polity(world, leader.id, leader.settlement_id)
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
            name="Rival Debug Camp",
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
            name="Rival Debug Ring",
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
        _declare_war(world, polity_ids[0], polity_ids[1])
        settlement = world.settlements[leader.settlement_id]
        resident_id = next(npc_id for npc_id in settlement.resident_npc_ids if npc_id != leader.id)
        packet_id = emit_command_packet(world, leader.id, settlement.id, "muster_force")
        world.history_index["packet_deliveries"][packet_id] = [resident_id]
        run_political_phase(world.clone_for_phase(), world)
        debug_lines = debug_grade_step_report(world, world.current_step)
        self.assertTrue(any(line.startswith("war_command:") for line in debug_lines))

    def test_war_supply_applies_war_burden_relation_template(self) -> None:
        world = create_world(default_config(seed=65))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        _found_polity(world, leader.id, leader.settlement_id)
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
            name="War Burden Camp",
            core_tile_id=target_tile,
            member_tile_ids=[target_tile],
            resident_npc_ids=[],
            stored_resources={"food": 18.0, "wood": 8.0, "ore": 3.0, "wealth": 4.0},
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
            name="War Burden Ring",
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
        for polity_id in polity_ids:
            polity = world.polities[polity_id]
            polity.treasury.update({"food": 6.0, "wood": 3.0, "ore": 1.5, "wealth": 2.0})
        resident_id = next(npc_id for npc_id in world.settlements[leader.settlement_id].resident_npc_ids if npc_id != leader.id)
        before = world.npcs[resident_id].relationships.get(leader.id)
        before_grievance = before.grievance if before else 0.0
        before_fear = before.fear if before else 0.0
        _declare_war(world, polity_ids[0], polity_ids[1])
        run_political_phase(world.clone_for_phase(), world)
        relation = world.npcs[resident_id].relationships[leader.id]
        self.assertGreater(relation.grievance, before_grievance)
        self.assertGreater(relation.fear, before_fear)
        self.assertTrue(any(entry["template"] == "war_burden" for entry in world.history_index["relation_log"]))

    def test_war_logs_materialize_into_events_and_belief_packets(self) -> None:
        world = create_world(default_config(seed=66))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        _found_polity(world, leader.id, leader.settlement_id)
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
            name="War Event Camp",
            core_tile_id=target_tile,
            member_tile_ids=[target_tile],
            resident_npc_ids=[],
            stored_resources={"food": 6.0, "wood": 1.0, "ore": 0.5, "wealth": 2.0},
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
            name="War Event Ring",
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
        for polity_id in polity_ids:
            polity = world.polities[polity_id]
            polity.treasury.update({"food": 0.0, "wood": 0.0, "ore": 0.0, "wealth": 0.0})
            for settlement_id in polity.member_settlement_ids:
                world.settlements[settlement_id].stored_resources.update({"food": 0.8, "wood": 0.2, "ore": 0.1, "wealth": 0.0})
        _declare_war(world, polity_ids[0], polity_ids[1])
        settlement = world.settlements[leader.settlement_id]
        resident_id = next(npc_id for npc_id in settlement.resident_npc_ids if npc_id != leader.id)
        packet_id = emit_command_packet(world, leader.id, settlement.id, "muster_force")
        world.history_index["packet_deliveries"][packet_id] = [resident_id]
        run_political_phase(world.clone_for_phase(), world)
        run_event_phase(world.clone_for_phase(), world)
        event_types = {event.event_type for event in world.events.values()}
        self.assertIn("WAR_SUPPLY_SHORTFALL", event_types)
        self.assertIn("WAR_COMMAND_MUSTERED", event_types)
        self.assertTrue(
            any(packet.content_domain == "belief" and packet.subject_ref in {"destiny", "legitimacy_form"} for packet in world.info_packets)
        )
        self.assertTrue(world.history_index["memory_conversion_log"])

    def test_event_packets_preserve_specific_event_type_in_perception(self) -> None:
        world = create_world(default_config(seed=67))
        npc_id = next(iter(world.npcs))
        event_id = world.next_id("event")
        world.events[event_id] = Event(
            id=event_id,
            event_type="WAR_SUPPLY_SHORTFALL",
            timestamp_step=world.current_step,
            location_tile_id=world.npcs[npc_id].location_tile_id,
            region_ref=None,
            participant_ids=[npc_id],
            cause_refs=["war:1"],
            outcome_summary_code="ratio=0.3",
            importance=72.0,
            visibility_scope="local",
            derived_memory_ids=[],
            derived_modifier_ids=[],
            derived_info_packet_ids=[],
        )
        emit_info_packet(
            world,
            source_event_id=event_id,
            origin_actor_id=npc_id,
            content_domain="event",
            subject_ref="war:1",
            location_ref=world.npcs[npc_id].location_tile_id,
            strength=40.0,
            visibility_scope="local",
            ttl=3,
            truth_alignment=1.0,
            propagation_channels=["spatial"],
        )
        propagate_info_packets(world)
        self.assertTrue(
            any(entry.summary_code == "WAR_SUPPLY_SHORTFALL" for entry in world.npcs[npc_id].perceived_state.perceived_recent_events)
        )

    def test_debug_view_surfaces_legitimacy_source_mix(self) -> None:
        world = create_world(default_config(seed=68))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        _found_polity(world, leader.id, leader.settlement_id)
        run_political_phase(world.clone_for_phase(), world)
        debug_lines = debug_grade_step_report(world, world.current_step)
        self.assertTrue(any(line.startswith("legitimacy_source:") for line in debug_lines))

    def test_player_knowledge_gates_unknown_entity_details(self) -> None:
        world = create_world(default_config(seed=69))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        _found_polity(world, leader.id, leader.settlement_id)
        polity_id = next(iter(world.polities))
        run_event_phase(world.clone_for_phase(), world)
        world.player_state.known_entities.discard(polity_id)
        lines = player_grade_polity_summary(world, polity_id)
        known_lines = player_grade_known_entities(world)
        self.assertTrue(any("visibility=rumored" in line for line in lines))
        self.assertTrue(any(line.startswith("known_entities=") for line in known_lines))

    def test_player_grade_recent_factor_views_surface_known_causes(self) -> None:
        world = create_world(default_config(seed=70))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        _found_polity(world, leader.id, leader.settlement_id)
        polity_id = next(iter(world.polities))
        settlement_id = leader.settlement_id
        run_political_phase(world.clone_for_phase(), world)
        polity_lines = player_grade_polity_recent_factors(world, polity_id)
        settlement_lines = player_grade_settlement_recent_factors(world, settlement_id)
        self.assertTrue(any(line.startswith("legitimacy_mix:") for line in polity_lines))
        self.assertTrue(any(line.startswith("flow:") for line in settlement_lines))

    def test_player_war_recent_factors_surface_supply_and_command(self) -> None:
        world = create_world(default_config(seed=71))
        leader = max(world.npcs.values(), key=lambda npc: npc.office_rank)
        _found_polity(world, leader.id, leader.settlement_id)
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
            name="War Why Camp",
            core_tile_id=target_tile,
            member_tile_ids=[target_tile],
            resident_npc_ids=[],
            stored_resources={"food": 6.0, "wood": 1.0, "ore": 0.5, "wealth": 2.0},
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
            name="War Why Ring",
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
        _declare_war(world, polity_ids[0], polity_ids[1])
        settlement = world.settlements[leader.settlement_id]
        resident_id = next(npc_id for npc_id in settlement.resident_npc_ids if npc_id != leader.id)
        packet_id = emit_command_packet(world, leader.id, settlement.id, "muster_force")
        world.history_index["packet_deliveries"][packet_id] = [resident_id]
        run_political_phase(world.clone_for_phase(), world)
        war_id = next(iter(world.war_states))
        war_lines = player_grade_war_recent_factors(world, war_id)
        self.assertTrue(any(line.startswith("supply:") for line in war_lines))
        self.assertTrue(any(line.startswith("command:") for line in war_lines))


if __name__ == "__main__":
    unittest.main()
