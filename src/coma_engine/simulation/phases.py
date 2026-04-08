from __future__ import annotations

from collections import defaultdict

from coma_engine.actions.catalog import ACTION_TEMPLATES
from coma_engine.actions.models import Action, ActionOutcome, AvailabilityDecision, ContestScore
from coma_engine.core.enums import ActionStatus
from coma_engine.core.state import WorldState
from coma_engine.core.transfers import (
    assign_npc_faction,
    assign_npc_polity,
    assign_npc_settlement,
    assign_settlement_faction,
    assign_settlement_polity,
    move_npc_to_tile,
    reconcile_references,
    validate_reference_consistency,
)
from coma_engine.models.entities import Faction, Goal, NPC, Polity, RelationEntry, Settlement, WarState
from coma_engine.models.perception import (
    BeliefSignalPerception,
    OpportunityPerception,
    PerceivedState,
    PowerMapPerception,
    RecentEventPerception,
    RelationShiftPerception,
    ResourceSignalPerception,
    ThreatPerception,
)
from coma_engine.systems.events import materialize_outcomes
from coma_engine.systems.modifiers import active_modifiers_for, apply_modifier_pipeline, tick_modifier_lifecycles
from coma_engine.systems.propagation import emit_command_packet, emit_info_packet, propagate_info_packets
from coma_engine.systems.relations import apply_relation_template_between, compute_group_salience
from coma_engine.systems.spatial import shortest_path_cost, traversable_neighbors


def _is_labor_eligible(world: WorldState, npc) -> bool:
    params = world.config.balance_parameters
    return npc.alive and params.labor_age_min <= npc.age <= params.labor_age_max


def _is_combat_eligible(world: WorldState, npc) -> bool:
    params = world.config.balance_parameters
    return npc.alive and params.combat_age_min <= npc.age <= params.combat_age_max


def _settlement_population_profile(world: WorldState, settlement_id: str) -> dict[str, float]:
    settlement = world.settlements[settlement_id]
    residents = [world.npcs[npc_id] for npc_id in settlement.resident_npc_ids if npc_id in world.npcs and world.npcs[npc_id].alive]
    return {
        "total": float(len(residents)),
        "labor": float(sum(1 for npc in residents if _is_labor_eligible(world, npc))),
        "combat": float(sum(1 for npc in residents if _is_combat_eligible(world, npc))),
    }


def _polity_population_profile(world: WorldState, polity_id: str) -> dict[str, float]:
    totals = {"total": 0.0, "labor": 0.0, "combat": 0.0}
    polity = world.polities[polity_id]
    for settlement_id in polity.member_settlement_ids:
        if settlement_id not in world.settlements:
            continue
        profile = _settlement_population_profile(world, settlement_id)
        for key in totals:
            totals[key] += profile[key]
    return totals


def _resource_value_rates() -> dict[str, float]:
    return {"wealth": 1.0, "food": 0.2, "wood": 0.15, "ore": 0.25}


def _extract_value_bundle(stock: dict[str, float], target_value: float) -> tuple[dict[str, float], float]:
    extracted = {"food": 0.0, "wood": 0.0, "ore": 0.0, "wealth": 0.0}
    remaining = max(0.0, target_value)
    rates = _resource_value_rates()
    for resource in ("wealth", "food", "wood", "ore"):
        if remaining <= 0.0:
            break
        rate = rates[resource]
        available = stock.get(resource, 0.0)
        if available <= 0.0:
            continue
        max_value = available * rate
        take_value = min(remaining, max_value)
        take_amount = take_value / rate
        stock[resource] = max(0.0, available - take_amount)
        extracted[resource] += take_amount
        remaining -= take_value
    extracted_value = sum(extracted[resource] * rates[resource] for resource in extracted)
    return extracted, extracted_value


def _merge_resource_bundle(target: dict[str, float], incoming: dict[str, float], scale: float = 1.0) -> None:
    for resource, amount in incoming.items():
        target[resource] = target.get(resource, 0.0) + amount * scale


def _bundle_value(bundle: dict[str, float]) -> float:
    rates = _resource_value_rates()
    return sum(bundle.get(resource, 0.0) * rates[resource] for resource in rates)


def _scaled_bundle(bundle: dict[str, float], scale: float) -> dict[str, float]:
    return {resource: amount * scale for resource, amount in bundle.items()}


def _rounded_bundle(bundle: dict[str, float]) -> dict[str, float]:
    return {resource: round(amount, 2) for resource, amount in bundle.items()}


def _executor_alignment_score(world: WorldState, executor_id: str, polity: Polity, settlement: Settlement) -> float:
    executor = world.npcs[executor_id]
    relation = executor.relationships.get(polity.ruler_npc_id, RelationEntry())
    score = 45.0
    score += relation.trust * 0.35
    score += relation.fear * 0.15
    score -= relation.grievance * 0.4
    score += executor.office_rank * 3.0
    score += settlement.stability * 0.1
    if executor.faction_id and executor.faction_id == polity.ruling_faction_id:
        score += 15.0
    elif settlement.faction_id and settlement.faction_id != polity.ruling_faction_id:
        score -= 12.0
    return world.clamp_metric(score)


def _translate_command_mode(world: WorldState, command_subject: str, alignment: float, packet_distortion: float) -> tuple[str, float, float]:
    params = world.config.balance_parameters
    effective_alignment = max(0.0, alignment - packet_distortion * 30.0)
    compliance = max(0.15, min(1.0, effective_alignment / 100.0))
    skim_rate = 0.0
    if effective_alignment < params.command_resistance_threshold:
        return "resist", compliance * 0.35, 0.0
    if effective_alignment < params.command_skimming_threshold:
        skim_rate = params.command_skim_base_rate + (params.command_skimming_threshold - effective_alignment) / 200.0
        return "skim", compliance * 0.7, min(0.45, skim_rate)
    if command_subject == "suppress_unrest" and effective_alignment < 65.0:
        return "soften", compliance * 0.75, 0.0
    return "comply", compliance, 0.0


def run_environment_phase(snapshot: WorldState, working: WorldState) -> None:
    _activate_delayed_effects(working)
    for tile in working.tiles.values():
        tile.current_stock["food"] = tile.current_stock.get("food", 0.0) + (
            tile.base_yield.get("food", 0.0) * working.config.balance_parameters.tile_regen_rate
        )
    tick_modifier_lifecycles(working)
    for packet in working.info_packets:
        packet.propagated_this_step = False
    _advance_demographics(working)


def _advance_demographics(world: WorldState) -> None:
    params = world.config.balance_parameters
    demographic_log: list[dict[str, object]] = world.history_index["demographic_log"]  # type: ignore[assignment]
    active_war_polities = {
        polity_id
        for war in world.war_states.values()
        if war.status == "active"
        for polity_id in war.participant_polity_ids
    }

    for npc in world.npcs.values():
        if not npc.alive:
            continue
        npc.age += params.age_increment_per_step
        tile = world.tiles[npc.location_tile_id]
        mortality = params.base_mortality_probability
        if npc.age > params.old_age_start:
            mortality += (npc.age - params.old_age_start) * params.old_age_mortality_scale
        mortality += max(0.0, (30.0 - npc.health) / 1000.0)
        mortality += tile.danger / 5000.0
        if npc.polity_id in active_war_polities and _is_combat_eligible(world, npc):
            mortality += params.war_attrition_scale * 0.2
        if world.rng.random() < mortality:
            npc.alive = False
            npc.current_action_ref = None
            demographic_log.append(
                {
                    "step": world.current_step,
                    "kind": "death",
                    "npc_id": npc.id,
                    "location_ref": npc.location_tile_id,
                    "family_id": npc.family_id,
                    "culture_id": npc.culture_id,
                }
            )

    for settlement in list(world.settlements.values()):
        profile = _settlement_population_profile(world, settlement.id)
        if profile["labor"] < 2.0 or settlement.stored_resources.get("food", 0.0) < params.birth_food_threshold:
            continue
        if world.rng.random() > params.settlement_birth_probability:
            continue
        parents = [
            world.npcs[npc_id]
            for npc_id in settlement.resident_npc_ids
            if npc_id in world.npcs and _is_labor_eligible(world, world.npcs[npc_id])
        ]
        if not parents:
            continue
        parent = world.rng.choice(parents)
        npc_id = world.next_id("npc")
        newborn = NPC(
            id=npc_id,
            name=f"NPC {npc_id.split(':')[-1]}",
            alive=True,
            age=0.0,
            culture_id=parent.culture_id,
            family_id=parent.family_id,
            location_tile_id=settlement.core_tile_id,
            health=88.0,
            settlement_id=None,
            faction_id=None,
            polity_id=None,
            role="child",
            office_rank=0,
            personal_inventory={"food": 0.0, "wood": 0.0, "ore": 0.0, "wealth": 0.0},
            needs={"food": 25.0, "safety": 20.0, "social": 20.0, "status": 5.0, "meaning": 5.0},
            personality=dict(parent.personality),
            abilities={"foraging": 10.0, "mobility": 12.0, "politics": 0.0, "warfare": 0.0},
            beliefs=dict(parent.beliefs),
            relationships={parent.id: RelationEntry(affinity=30.0, trust=20.0, familiarity=30.0)},
            memory_ids=[],
            long_term_goal=Goal(goal_type="SURVIVE"),
            active_modifier_ids=[],
            cooldowns={},
            current_action_ref=None,
            perceived_state=PerceivedState(),
        )
        world.npcs[npc_id] = newborn
        if npc_id not in world.tiles[settlement.core_tile_id].resident_npc_ids:
            world.tiles[settlement.core_tile_id].resident_npc_ids.append(npc_id)
        assign_npc_settlement(world, npc_id, settlement.id)
        if settlement.faction_id:
            assign_npc_faction(world, npc_id, settlement.faction_id)
        if settlement.polity_id:
            assign_npc_polity(world, npc_id, settlement.polity_id)
        settlement.stored_resources["food"] = max(0.0, settlement.stored_resources.get("food", 0.0) - 1.0)
        demographic_log.append(
            {
                "step": world.current_step,
                "kind": "birth",
                "npc_id": npc_id,
                "location_ref": settlement.core_tile_id,
                "family_id": parent.family_id,
                "culture_id": parent.culture_id,
            }
        )


def run_resource_phase(snapshot: WorldState, working: WorldState) -> None:
    for settlement in working.settlements.values():
        settlement.net_production = {resource: 0.0 for resource in working.config.design_constants.resource_types}
        settlement.current_taxable_output = 0.0
        profile = _settlement_population_profile(working, settlement.id)
        settlement.labor_pool = profile["labor"]
    for npc in working.npcs.values():
        if not npc.alive:
            continue
        tile = working.tiles[npc.location_tile_id]
        tile_modifiers = active_modifiers_for(working, tile.id, "yield.food")
        allowed, yield_value, _ = apply_modifier_pipeline(tile.base_yield.get("food", 0.0), tile_modifiers)
        tile.effective_yield["food"] = yield_value if allowed else 0.0
        labor_factor = 1.0 if _is_labor_eligible(working, npc) else 0.0
        if npc.settlement_id and npc.settlement_id in working.settlements:
            settlement = working.settlements[npc.settlement_id]
            produced = min(tile.current_stock.get("food", 0.0), tile.effective_yield["food"] * 0.5 * labor_factor)
            tile.current_stock["food"] -= produced
            settlement.stored_resources["food"] = settlement.stored_resources.get("food", 0.0) + produced
            settlement.net_production["food"] += produced
        else:
            produced = min(tile.current_stock.get("food", 0.0), tile.effective_yield["food"] * 0.3 * labor_factor)
            tile.current_stock["food"] -= produced
            npc.personal_inventory["food"] = npc.personal_inventory.get("food", 0.0) + produced

    for npc in working.npcs.values():
        if not npc.alive:
            continue
        remaining_need = working.config.balance_parameters.stock_consumption_per_npc
        if npc.settlement_id and npc.settlement_id in working.settlements:
            settlement = working.settlements[npc.settlement_id]
            consumed = min(settlement.stored_resources.get("food", 0.0), remaining_need)
            settlement.stored_resources["food"] = settlement.stored_resources.get("food", 0.0) - consumed
            remaining_need -= consumed
        if remaining_need > 0:
            consumed = min(npc.personal_inventory.get("food", 0.0), remaining_need)
            npc.personal_inventory["food"] = npc.personal_inventory.get("food", 0.0) - consumed


def run_need_update_phase(snapshot: WorldState, working: WorldState) -> None:
    params = working.config.balance_parameters
    for npc in working.npcs.values():
        if not npc.alive:
            continue
        stock = npc.personal_inventory.get("food", 0.0)
        settlement_stock = 0.0
        if npc.settlement_id and npc.settlement_id in working.settlements:
            settlement_stock = working.settlements[npc.settlement_id].stored_resources.get("food", 0.0)
        npc.needs["food"] = working.clamp_metric(max(0.0, 100.0 - (stock + settlement_stock * 0.3) * 10.0))
        npc.needs["safety"] = working.clamp_metric(working.tiles[npc.location_tile_id].danger + params.safety_need_decay)
        npc.needs["social"] = working.clamp_metric(npc.needs.get("social", 30.0) + params.social_need_decay * 0.2)
        npc.needs["status"] = working.clamp_metric(40.0 - npc.office_rank * 5.0 + params.status_need_decay * 0.5)
        npc.needs["meaning"] = working.clamp_metric(
            35.0 - npc.beliefs.get("destiny", 0.0) * 0.2 + params.meaning_need_decay * 0.5
        )


def run_information_phase(snapshot: WorldState, working: WorldState) -> None:
    for npc in working.npcs.values():
        npc.perceived_state.prune(working.current_step)
        _refresh_local_perception(working, npc)
    propagate_info_packets(working)


def _refresh_local_perception(world: WorldState, npc) -> None:
    state = npc.perceived_state
    expires = world.current_step + world.config.balance_parameters.default_perception_ttl
    visible_tiles = [npc.location_tile_id, *traversable_neighbors(world, npc.location_tile_id)]
    resource_entries = [
        ResourceSignalPerception(
            location_ref=tile_id,
            resource_type="food",
            abundance_signal=world.tiles[tile_id].current_stock.get("food", 0.0)
            + world.tiles[tile_id].base_yield.get("food", 0.0) * 4.0,
            source_ref=f"local:{tile_id}",
            credibility=1.0,
            expires_step=expires,
        )
        for tile_id in visible_tiles
    ]
    state.perceived_resource_signals = sorted(
        resource_entries,
        key=lambda entry: entry.abundance_signal,
        reverse=True,
    )[: world.config.balance_parameters.perception_channel_capacity]

    threat_entries = [
        ThreatPerception(
            subject_ref=tile_id,
            location_ref=tile_id,
            threat_strength=world.tiles[tile_id].danger,
            source_ref=f"local:{tile_id}",
            credibility=1.0,
            expires_step=expires,
        )
        for tile_id in visible_tiles
    ]
    state.perceived_threats = sorted(
        threat_entries,
        key=lambda entry: entry.threat_strength,
        reverse=True,
    )[: world.config.balance_parameters.perception_channel_capacity]

    opportunity_entries = [
        OpportunityPerception(
            subject_ref=tile_id,
            location_ref=tile_id,
            opportunity_kind="forage" if tile_id == npc.location_tile_id else "move",
            estimated_benefit=world.tiles[tile_id].base_yield.get("food", 0.0) * 10.0,
            source_ref=f"local:{tile_id}",
            credibility=1.0,
            expires_step=expires,
        )
        for tile_id in visible_tiles
    ]
    state.perceived_opportunities = sorted(
        opportunity_entries,
        key=lambda entry: entry.estimated_benefit,
        reverse=True,
    )[: world.config.balance_parameters.perception_channel_capacity]

    local_power: list[PowerMapPerception] = []
    for other in world.npcs.values():
        if other.location_tile_id in visible_tiles and other.id != npc.id:
            power_score = other.office_rank * 15.0 + other.abilities.get("politics", 0.0) * 0.4
            local_power.append(
                PowerMapPerception(
                    subject_ref=other.id,
                    power_score=power_score,
                    rank_hint=other.office_rank,
                    source_ref="local_observation",
                    credibility=1.0,
                    expires_step=expires,
                )
            )
    state.perceived_power_map = sorted(
        local_power,
        key=lambda entry: entry.power_score,
        reverse=True,
    )[: world.config.balance_parameters.perception_channel_capacity]
    relation_log: list[dict[str, object]] = world.history_index["relation_log"]  # type: ignore[assignment]
    relation_entries = [
        RelationShiftPerception(
            subject_ref=str(entry["target_id"]),
            summary_code=str(entry["template"]),
            delta_strength=float(entry["scale"]) * 10.0,
            source_ref=f"relation:{entry['source_id']}",
            credibility=1.0,
            expires_step=expires,
        )
        for entry in relation_log[-12:]
        if entry["source_id"] == npc.id or entry["target_id"] == npc.id
    ]
    state.perceived_relations_shift = relation_entries[: world.config.balance_parameters.perception_channel_capacity]
    belief_entries: list[BeliefSignalPerception] = []
    if npc.polity_id and npc.polity_id in world.polities:
        polity = world.polities[npc.polity_id]
        belief_entries.append(
            BeliefSignalPerception(
                belief_domain="legitimacy_form",
                signal_strength=polity.legitimacy_components.get("support", 0.0),
                source_ref=f"polity:{polity.id}",
                credibility=1.0,
                expires_step=expires,
            )
        )
        belief_entries.append(
            BeliefSignalPerception(
                belief_domain="destiny",
                signal_strength=max(0.0, 60.0 - polity.legitimacy_components.get("war_strain", 0.0)),
                source_ref=f"polity:{polity.id}:war_strain",
                credibility=0.8,
                expires_step=expires,
            )
        )
    state.perceived_belief_signals = belief_entries[: world.config.balance_parameters.perception_channel_capacity]
    state.perceived_recent_events = state.perceived_recent_events[
        : world.config.balance_parameters.perception_channel_capacity
    ]


def _visible_tiles_for(world: WorldState, npc_id: str) -> set[str]:
    npc = world.npcs[npc_id]
    return {npc.location_tile_id, *traversable_neighbors(world, npc.location_tile_id)}


def _visible_settlements_for(world: WorldState, npc_id: str) -> set[str]:
    visible: set[str] = set()
    for tile_id in _visible_tiles_for(world, npc_id):
        tile = world.tiles[tile_id]
        if tile.settlement_id:
            visible.add(tile.settlement_id)
    return visible


def _visible_polities_for(world: WorldState, npc_id: str) -> set[str]:
    visible: set[str] = set()
    for settlement_id in _visible_settlements_for(world, npc_id):
        settlement = world.settlements.get(settlement_id)
        if settlement and settlement.polity_id:
            visible.add(settlement.polity_id)
    for tile_id in _visible_tiles_for(world, npc_id):
        for resident_id in world.tiles[tile_id].resident_npc_ids:
            other = world.npcs[resident_id]
            if other.polity_id:
                visible.add(other.polity_id)
    return visible


def _availability_decision(world: WorldState, npc_id: str, action_type: str, target_ref: str | None) -> AvailabilityDecision:
    npc = world.npcs[npc_id]
    visible_tiles = _visible_tiles_for(world, npc_id)
    visible_settlements = _visible_settlements_for(world, npc_id)
    visible_polities = _visible_polities_for(world, npc_id)

    if not npc.alive:
        return AvailabilityDecision(False, "actor_dead")

    if action_type == "FORAGE":
        return AvailabilityDecision(True, "basic_survival")
    if action_type == "MOVE":
        allowed = target_ref is not None and target_ref in traversable_neighbors(world, npc.location_tile_id)
        return AvailabilityDecision(allowed, "movement" if allowed else "movement_blocked")
    if action_type == "SCOUT":
        allowed = target_ref is not None and target_ref in traversable_neighbors(world, npc.location_tile_id)
        return AvailabilityDecision(allowed, "scouting" if allowed else "scouting_blocked")
    if action_type == "MIGRATE":
        if target_ref is None or target_ref not in visible_tiles or target_ref == npc.location_tile_id:
            return AvailabilityDecision(False, "migration_target_invalid")
        if target_ref not in traversable_neighbors(world, npc.location_tile_id):
            return AvailabilityDecision(False, "migration_path_invalid")
        return AvailabilityDecision(True, "migrate")
    if action_type == "TRADE":
        if not npc.settlement_id or target_ref is None or target_ref == npc.settlement_id:
            return AvailabilityDecision(False, "trade_requires_external_settlement")
        if target_ref not in visible_settlements:
            return AvailabilityDecision(False, "trade_target_not_visible")
        return AvailabilityDecision(True, "trade")
    if action_type == "FOUND_POLITY":
        if npc.office_rank < world.config.balance_parameters.low_rank_high_politics_gate_rank:
            return AvailabilityDecision(False, "rank_too_low")
        if not npc.settlement_id or not npc.faction_id:
            return AvailabilityDecision(False, "missing_organization_base")
        settlement = world.settlements[npc.settlement_id]
        faction = world.factions[npc.faction_id]
        if settlement.polity_id:
            return AvailabilityDecision(False, "already_under_polity")
        allowed = (
            faction.support_score >= world.config.balance_parameters.polity_entry_support
            and faction.cohesion >= world.config.balance_parameters.polity_entry_support
            and settlement.stability >= world.config.balance_parameters.polity_entry_stability
        )
        return AvailabilityDecision(allowed, "found_polity" if allowed else "found_polity_threshold_failed")
    if action_type == "FORMAL_TAX_ORDER":
        allowed = (
            npc.polity_id is not None
            and npc.office_rank >= world.config.balance_parameters.low_rank_high_politics_gate_rank
            and target_ref in world.settlements
            and world.settlements[target_ref].polity_id == npc.polity_id
        )
        return AvailabilityDecision(allowed, "formal_tax_order" if allowed else "tax_order_unavailable")
    if action_type == "LEVY_RESOURCES":
        allowed = (
            npc.polity_id is not None
            and npc.office_rank >= world.config.balance_parameters.low_rank_high_politics_gate_rank
            and target_ref in world.settlements
            and world.settlements[target_ref].polity_id == npc.polity_id
        )
        return AvailabilityDecision(allowed, "resource_levy" if allowed else "resource_levy_unavailable")
    if action_type == "MUSTER_FORCE":
        allowed = (
            npc.polity_id is not None
            and npc.office_rank >= world.config.balance_parameters.low_rank_high_politics_gate_rank
            and target_ref in world.settlements
            and world.settlements[target_ref].polity_id == npc.polity_id
        )
        return AvailabilityDecision(allowed, "muster_force" if allowed else "muster_force_unavailable")
    if action_type == "SUPPRESS_UNREST":
        allowed = (
            npc.polity_id is not None
            and npc.office_rank >= world.config.balance_parameters.low_rank_high_politics_gate_rank
            and target_ref in world.settlements
            and world.settlements[target_ref].polity_id == npc.polity_id
        )
        return AvailabilityDecision(allowed, "suppress_unrest" if allowed else "suppress_unrest_unavailable")
    if action_type == "DECLARE_WAR":
        allowed = (
            npc.polity_id is not None
            and npc.office_rank >= world.config.balance_parameters.low_rank_high_politics_gate_rank + 1
            and target_ref in visible_polities
            and target_ref != npc.polity_id
        )
        return AvailabilityDecision(allowed, "declare_war" if allowed else "war_target_unavailable")
    return AvailabilityDecision(False, "unsupported_action")


def _availability_for(world: WorldState, npc_id: str, action_type: str, target_ref: str | None) -> bool:
    return _availability_decision(world, npc_id, action_type, target_ref).allowed


def _action_target_ref(action: Action) -> str | None:
    for ref in (
        action.target_npc_id,
        action.target_tile_id,
        action.target_settlement_id,
        action.target_faction_id,
        action.target_polity_id,
    ):
        if ref:
            return ref
    return None


def _action_resource_cost(action_type: str) -> dict[str, float]:
    if action_type in {"SCOUT", "MOVE"}:
        return {"food": 0.2, "wood": 0.0, "ore": 0.0, "wealth": 0.0}
    if action_type == "MIGRATE":
        return {"food": 0.6, "wood": 0.0, "ore": 0.0, "wealth": 0.0}
    if action_type == "TRADE":
        return {"food": 0.4, "wood": 0.0, "ore": 0.0, "wealth": 0.2}
    if action_type == "FOUND_POLITY":
        return {"food": 0.8, "wood": 0.2, "ore": 0.0, "wealth": 0.8}
    if action_type in {"FORMAL_TAX_ORDER", "LEVY_RESOURCES"}:
        return {"food": 0.0, "wood": 0.0, "ore": 0.0, "wealth": 0.2}
    if action_type == "DECLARE_WAR":
        return {"food": 0.5, "wood": 0.0, "ore": 0.0, "wealth": 1.0}
    if action_type == "MUSTER_FORCE":
        return {"food": 0.6, "wood": 0.2, "ore": 0.1, "wealth": 0.4}
    if action_type == "SUPPRESS_UNREST":
        return {"food": 0.3, "wood": 0.1, "ore": 0.0, "wealth": 0.4}
    return {"food": 0.0, "wood": 0.0, "ore": 0.0, "wealth": 0.0}


def _perceived_resource_score(npc, location_ref: str | None) -> float:
    if location_ref is None:
        return 0.0
    for entry in npc.perceived_state.perceived_resource_signals:
        if entry.location_ref == location_ref:
            return entry.abundance_signal
    return 0.0


def _perceived_threat_score(npc, location_ref: str | None) -> float:
    if location_ref is None:
        return 0.0
    for entry in npc.perceived_state.perceived_threats:
        if entry.location_ref == location_ref:
            return entry.threat_strength
    return 0.0


def _perceived_belief_score(npc, belief_domain: str) -> float:
    total = 0.0
    for entry in npc.perceived_state.perceived_belief_signals:
        if entry.belief_domain == belief_domain:
            total += entry.signal_strength * entry.credibility
    return total


def _perceived_recent_event_score(npc, summary_code: str) -> float:
    total = 0.0
    for entry in npc.perceived_state.perceived_recent_events:
        if entry.summary_code == summary_code:
            total += entry.importance * entry.credibility
    return total


def _score_action(world: WorldState, npc_id: str, action_type: str, target_ref: str | None) -> dict[str, float]:
    npc = world.npcs[npc_id]
    local_polity_conflict = 0.0
    if npc.settlement_id and npc.settlement_id in world.settlements:
        settlement = world.settlements[npc.settlement_id]
        if settlement.polity_id and settlement.polity_id != npc.polity_id:
            local_polity_conflict = 10.0
    scores = {
        "need_gain": 0.0,
        "goal_progress": 0.0,
        "relationship_delta": 0.0,
        "organization_conflict_cost": 0.0,
        "resource_cost": 0.0,
        "path_cost": 0.0,
        "risk_penalty": 0.0,
        "belief_consistency": 0.0,
        "modifier_impact": 0.0,
        "salience_conflict_penalty": 0.0,
    }
    if action_type == "FORAGE":
        scores["need_gain"] = npc.needs["food"] * 0.9
        scores["path_cost"] = 1.0
        scores["risk_penalty"] = _perceived_threat_score(npc, npc.location_tile_id) * 0.15
        scores["belief_consistency"] = npc.beliefs.get("destiny", 0.0) * 0.05
    elif action_type == "MOVE" and target_ref:
        scores["need_gain"] = _perceived_resource_score(npc, target_ref) * 1.2
        scores["path_cost"] = shortest_path_cost(world, npc.location_tile_id, target_ref) * 6.0
        scores["risk_penalty"] = _perceived_threat_score(npc, target_ref) * 0.1
    elif action_type == "SCOUT" and target_ref:
        scores["goal_progress"] = 16.0
        scores["need_gain"] = _perceived_resource_score(npc, target_ref) * 0.25
        scores["path_cost"] = shortest_path_cost(world, npc.location_tile_id, target_ref) * 4.0
        scores["risk_penalty"] = _perceived_threat_score(npc, target_ref) * 0.2
        scores["goal_progress"] += _perceived_recent_event_score(npc, "event") * 0.15
    elif action_type == "MIGRATE" and target_ref:
        scores["need_gain"] = _perceived_resource_score(npc, target_ref) * 0.8 + npc.needs["safety"] * 0.35
        scores["path_cost"] = shortest_path_cost(world, npc.location_tile_id, target_ref) * 8.0
        scores["risk_penalty"] = _perceived_threat_score(npc, target_ref) * 0.08
        scores["organization_conflict_cost"] = 8.0 if npc.settlement_id else 0.0
    elif action_type == "TRADE" and target_ref:
        scores["goal_progress"] = 18.0
        scores["relationship_delta"] = 10.0
        scores["resource_cost"] = 4.0
        scores["organization_conflict_cost"] = local_polity_conflict
    elif action_type == "FOUND_POLITY":
        scores["goal_progress"] = 60.0 if npc.long_term_goal.goal_type == "FOUND_POLITY" else 25.0
        scores["belief_consistency"] = npc.beliefs.get("destiny", 0.0) * 0.4
        scores["belief_consistency"] += _perceived_belief_score(npc, "legitimacy_form") * 0.1
        scores["risk_penalty"] = 25.0
        scores["organization_conflict_cost"] = max(0.0, 50.0 - compute_group_salience(world, npc)["faction"])
    elif action_type == "FORMAL_TAX_ORDER":
        scores["goal_progress"] = 24.0
        scores["organization_conflict_cost"] = 10.0
    elif action_type == "LEVY_RESOURCES":
        scores["goal_progress"] = 20.0
        scores["organization_conflict_cost"] = 14.0
        scores["risk_penalty"] = 6.0
    elif action_type == "DECLARE_WAR":
        scores["goal_progress"] = 18.0
        scores["risk_penalty"] = 30.0
    elif action_type == "MUSTER_FORCE":
        scores["goal_progress"] = 26.0
        scores["organization_conflict_cost"] = 18.0
        scores["resource_cost"] = 8.0
    elif action_type == "SUPPRESS_UNREST":
        scores["goal_progress"] = 20.0 + npc.needs["safety"] * 0.2
        scores["organization_conflict_cost"] = 12.0
        scores["risk_penalty"] = 5.0
        scores["belief_consistency"] = npc.beliefs.get("legitimacy_form", 0.0) * 0.08
    return scores


def _total_score(world: WorldState, score_breakdown: dict[str, float]) -> float:
    noise = world.rng.uniform(
        -world.config.balance_parameters.action_noise_amplitude,
        world.config.balance_parameters.action_noise_amplitude,
    )
    return (
        score_breakdown["need_gain"]
        + score_breakdown["goal_progress"]
        + score_breakdown["relationship_delta"]
        + score_breakdown["belief_consistency"]
        + score_breakdown["modifier_impact"]
        - score_breakdown["organization_conflict_cost"]
        - score_breakdown["resource_cost"]
        - score_breakdown["path_cost"]
        - score_breakdown["risk_penalty"]
        - score_breakdown["salience_conflict_penalty"]
        + noise
    )


def _resolution_group_key(action_type: str, target_ref: str | None) -> str:
    return f"{action_type}:{target_ref or 'none'}"


def run_decision_phase(snapshot: WorldState, working: WorldState) -> None:
    explanations: dict[str, dict[str, float]] = {}
    for npc in working.npcs.values():
        if not npc.alive:
            continue
        if npc.current_action_ref and any(action.id == npc.current_action_ref for action in working.action_queue):
            continue
        npc.salience_scores = compute_group_salience(working, npc)
        action_space = [("FORAGE", npc.location_tile_id)]
        candidate_move_targets = {
            entry.location_ref
            for entry in npc.perceived_state.perceived_resource_signals
            if entry.location_ref in traversable_neighbors(working, npc.location_tile_id)
        }
        visible_settlements = _visible_settlements_for(working, npc.id)
        visible_polities = _visible_polities_for(working, npc.id)
        for adjacent_id in sorted(candidate_move_targets):
            action_space.append(("MOVE", adjacent_id))
            action_space.append(("SCOUT", adjacent_id))
            if npc.needs["food"] >= 45.0 or npc.needs["safety"] >= 40.0:
                action_space.append(("MIGRATE", adjacent_id))
        for settlement_id in sorted(visible_settlements):
            if settlement_id != npc.settlement_id:
                action_space.append(("TRADE", settlement_id))
        if npc.settlement_id:
            action_space.append(("FOUND_POLITY", npc.settlement_id))
            action_space.append(("FORMAL_TAX_ORDER", npc.settlement_id))
            action_space.append(("LEVY_RESOURCES", npc.settlement_id))
            action_space.append(("MUSTER_FORCE", npc.settlement_id))
            action_space.append(("SUPPRESS_UNREST", npc.settlement_id))
        if npc.polity_id:
            for polity_id in sorted(visible_polities):
                if polity_id != npc.polity_id:
                    action_space.append(("DECLARE_WAR", polity_id))
                    break

        scored = []
        for action_type, target_ref in action_space:
            availability = _availability_decision(working, npc.id, action_type, target_ref)
            if not availability.allowed:
                continue
            breakdown = _score_action(working, npc.id, action_type, target_ref)
            scored.append((action_type, target_ref, breakdown, _total_score(working, breakdown)))
        scored.sort(key=lambda item: item[3], reverse=True)
        npc.candidate_actions = [item[0] for item in scored[: working.config.balance_parameters.debug_candidate_action_count]]
        npc.action_score_breakdown = {
            f"{item[0]}:{item[1]}": item[2]
            for item in scored[: working.config.balance_parameters.debug_candidate_action_count]
        }
        if scored:
            chosen_type, chosen_target, chosen_breakdown, _ = scored[0]
            explanations[npc.id] = chosen_breakdown
            template = ACTION_TEMPLATES[chosen_type]
            action = Action(
                id=working.next_id("action"),
                action_type=chosen_type,
                actor_id=npc.id,
                target_npc_id=chosen_target if chosen_target and chosen_target.startswith("npc:") else None,
                target_tile_id=chosen_target if chosen_target and chosen_target.startswith("tile:") else None,
                target_settlement_id=chosen_target if chosen_target and chosen_target.startswith("settlement:") else None,
                target_faction_id=chosen_target if chosen_target and chosen_target.startswith("faction:") else None,
                target_polity_id=chosen_target if chosen_target and chosen_target.startswith("polity:") else None,
                declared_step=working.current_step,
                priority_class=template.default_priority_class,
                duration_type=template.default_duration_type,
                estimated_duration=template.default_duration,
                resource_cost=_action_resource_cost(chosen_type),
                risk_value=chosen_breakdown["risk_penalty"],
                availability_rule_id=template.availability_rule_id,
                resolution_group_key=_resolution_group_key(chosen_type, chosen_target),
                status=ActionStatus.DECLARED.value,
            )
            working.action_queue.append(action)
            npc.current_action_ref = action.id
    action_explanations: dict[str, object] = working.history_index["action_explanations"]  # type: ignore[assignment]
    action_explanations[working.current_step] = explanations


def run_declaration_phase(snapshot: WorldState, working: WorldState) -> None:
    unique_ids = set()
    deduped = []
    for action in working.action_queue:
        target_ref = _action_target_ref(action)
        availability = _availability_decision(working, action.actor_id, action.action_type, target_ref)
        if (
            action.id not in unique_ids
            and action.status == ActionStatus.DECLARED.value
            and _validate_action_signature(action)
            and availability.allowed
        ):
            unique_ids.add(action.id)
            deduped.append(action)
    working.action_queue = deduped


def _validate_action_signature(action: Action) -> bool:
    template = ACTION_TEMPLATES.get(action.action_type)
    if template is None:
        return False
    signature = template.signature
    target_values = {
        "target_npc_id": action.target_npc_id,
        "target_tile_id": action.target_tile_id,
        "target_settlement_id": action.target_settlement_id,
        "target_faction_id": action.target_faction_id,
        "target_polity_id": action.target_polity_id,
    }
    for required in signature.required_targets:
        if not target_values.get(required):
            return False
    for forbidden in signature.forbidden_targets:
        if target_values.get(forbidden):
            return False
    if not signature.allow_targetless and not any(target_values.values()) and not signature.required_targets:
        return False
    return True


def run_resolution_phase(snapshot: WorldState, working: WorldState) -> None:
    declared = [action for action in working.action_queue if action.status == ActionStatus.DECLARED.value]
    valid_actions, invalid_outcomes = _validity_check(snapshot, declared)
    reserved_actions, reservation_outcomes = _resource_reservation(working, valid_actions)
    resolved = _contest_resolution(working, reserved_actions)
    _effect_application(working, resolved, invalid_outcomes + reservation_outcomes)
    _cleanup_and_hooks(working)


def _outcome_from_action(action: Action, result: str, cause_ref: str) -> ActionOutcome:
    return ActionOutcome(
        action_id=action.id,
        action_type=action.action_type,
        actor_id=action.actor_id,
        result=result,
        summary_code=f"{action.action_type.lower()}_{result}",
        participant_ids=[action.actor_id],
        cause_refs=[cause_ref],
        target_refs=[ref for ref in (_action_target_ref(action),) if ref],
        resource_delta=dict(action.resource_cost),
    )


def _validity_check(snapshot: WorldState, actions: list[Action]) -> tuple[list[Action], list[ActionOutcome]]:
    valid: list[Action] = []
    outcomes: list[ActionOutcome] = []
    for action in actions:
        if action.actor_id not in snapshot.npcs or not snapshot.npcs[action.actor_id].alive:
            action.status = ActionStatus.CANCELLED.value
            outcomes.append(_outcome_from_action(action, "cancelled", "actor_invalid"))
            continue
        target_ref = _action_target_ref(action)
        if not _validate_action_signature(action):
            action.status = ActionStatus.CANCELLED.value
            outcomes.append(_outcome_from_action(action, "cancelled", "signature_invalid"))
            continue
        availability = _availability_decision(snapshot, action.actor_id, action.action_type, target_ref)
        if not availability.allowed:
            action.status = ActionStatus.CANCELLED.value
            outcomes.append(_outcome_from_action(action, "cancelled", availability.reason_code))
            continue
        valid.append(action)
    return valid, outcomes


def _resource_reservation(working: WorldState, actions: list[Action]) -> tuple[list[Action], list[ActionOutcome]]:
    reserved: list[Action] = []
    outcomes: list[ActionOutcome] = []
    for action in actions:
        actor = working.npcs[action.actor_id]
        settlement = working.settlements.get(actor.settlement_id) if actor.settlement_id else None
        affordable = all(
            actor.personal_inventory.get(resource, 0.0) + (settlement.stored_resources.get(resource, 0.0) if settlement else 0.0)
            >= amount
            for resource, amount in action.resource_cost.items()
        )
        if not affordable:
            action.status = ActionStatus.FAILED.value
            outcomes.append(_outcome_from_action(action, "failed", "insufficient_resources"))
            continue
        for resource, amount in action.resource_cost.items():
            from_actor = min(actor.personal_inventory.get(resource, 0.0), amount)
            actor.personal_inventory[resource] = actor.personal_inventory.get(resource, 0.0) - from_actor
            remaining = amount - from_actor
            if remaining > 0.0 and settlement is not None:
                settlement.stored_resources[resource] = settlement.stored_resources.get(resource, 0.0) - remaining
        action.status = ActionStatus.RESERVED.value
        reserved.append(action)
    return reserved, outcomes


def _contest_resolution(working: WorldState, actions: list[Action]) -> list[tuple[Action, ContestScore, str]]:
    grouped: dict[str, list[Action]] = defaultdict(list)
    for action in actions:
        grouped[action.resolution_group_key].append(action)
    results: list[tuple[Action, ContestScore, str]] = []
    for group_actions in grouped.values():
        scored = []
        for action in group_actions:
            actor = working.npcs[action.actor_id]
            target_ref = _action_target_ref(action)
            ability_component = actor.abilities.get("politics", 0.0)
            if action.action_type in {"FORAGE", "SCOUT"}:
                ability_component = actor.abilities.get("foraging", 0.0)
            elif action.action_type in {"MOVE", "MIGRATE", "TRADE"}:
                ability_component = actor.abilities.get("mobility", 0.0)
            elif action.action_type in {"DECLARE_WAR", "MUSTER_FORCE"}:
                ability_component = actor.abilities.get("warfare", 0.0)

            support_component = 10.0 if actor.faction_id else 0.0
            if action.target_settlement_id and action.target_settlement_id in working.settlements:
                target_settlement = working.settlements[action.target_settlement_id]
                support_component += target_settlement.stability * 0.1
            if action.action_type in {"FORMAL_TAX_ORDER", "LEVY_RESOURCES", "MUSTER_FORCE"} and actor.polity_id:
                polity = working.polities.get(actor.polity_id)
                if polity:
                    support_component += polity.command_network_state.get("integrity", 0.0) * 0.1

            position_component = 5.0 if actor.settlement_id else 0.0
            if target_ref and isinstance(target_ref, str) and target_ref.startswith("tile:"):
                distance = shortest_path_cost(working, actor.location_tile_id, target_ref)
                if distance != float("inf"):
                    position_component -= distance * 2.0

            score = ContestScore(
                ability_component=ability_component,
                support_component=support_component,
                position_component=position_component,
                modifier_component=0.0,
                noise_component=working.rng.uniform(
                    -working.config.balance_parameters.action_noise_amplitude,
                    working.config.balance_parameters.action_noise_amplitude,
                ),
            )
            scored.append((action, score))
        scored.sort(key=lambda item: item[1].total, reverse=True)
        for index, (action, score) in enumerate(scored):
            results.append((action, score, "succeeded" if index == 0 else "failed"))
    return results


def _effect_application(
    working: WorldState,
    resolved: list[tuple[Action, ContestScore, str]],
    prior_outcomes: list[ActionOutcome],
) -> None:
    working.outcome_records = list(prior_outcomes)
    for action, _score, result in resolved:
        outcome_result = result
        template = ACTION_TEMPLATES[action.action_type]
        if result == "succeeded" and action.duration_type != "instant":
            if _should_interrupt_action(working, action):
                _refund_action_cost(working, action)
                action.status = ActionStatus.INTERRUPTED.value
                outcome_result = "interrupted"
            elif action.estimated_duration > 1:
                _emit_continuation_leak(working, action)
                action.status = ActionStatus.DECLARED.value
                outcome_result = "partial"
            else:
                _apply_success(working, action)
                action.status = ActionStatus.SUCCEEDED.value
        elif result == "succeeded":
            _apply_success(working, action)
            action.status = ActionStatus.SUCCEEDED.value
        else:
            if template.partial_refund_rate > 0.0:
                _refund_action_cost(working, action)
            action.status = ActionStatus.INTERRUPTED.value if action.duration_type != "instant" else ActionStatus.FAILED.value
            outcome_result = "interrupted" if action.duration_type != "instant" else "failed"
        working.outcome_records.append(
            ActionOutcome(
                action_id=action.id,
                action_type=action.action_type,
                actor_id=action.actor_id,
                result=outcome_result,
                summary_code=f"{action.action_type.lower()}_{outcome_result}",
                participant_ids=[action.actor_id],
                cause_refs=[],
                target_refs=[
                    ref
                    for ref in (
                        action.target_npc_id,
                        action.target_tile_id,
                        action.target_settlement_id,
                        action.target_faction_id,
                        action.target_polity_id,
                    )
                    if ref
                ],
                resource_delta=dict(action.resource_cost),
            )
        )


def _should_interrupt_action(working: WorldState, action: Action) -> bool:
    template = ACTION_TEMPLATES[action.action_type]
    if not template.interruptible:
        return False
    actor = working.npcs[action.actor_id]
    if actor.health < 25.0:
        return True
    current_threat = working.tiles[actor.location_tile_id].danger
    if current_threat >= template.interruption_threshold:
        return True
    if action.target_tile_id and action.target_tile_id in working.tiles:
        if working.tiles[action.target_tile_id].danger >= template.interruption_threshold:
            return True
    if action.target_settlement_id and action.target_settlement_id in working.settlements:
        settlement = working.settlements[action.target_settlement_id]
        local_resistance = max(0.0, 50.0 - settlement.stability)
        if local_resistance >= template.interruption_threshold:
            return True
    return False


def _refund_action_cost(working: WorldState, action: Action) -> None:
    template = ACTION_TEMPLATES[action.action_type]
    if template.partial_refund_rate <= 0.0:
        return
    actor = working.npcs[action.actor_id]
    for resource, amount in action.resource_cost.items():
        actor.personal_inventory[resource] = actor.personal_inventory.get(resource, 0.0) + amount * template.partial_refund_rate


def _emit_continuation_leak(working: WorldState, action: Action) -> None:
    if action.duration_type not in {"travel", "campaign", "scheme", "channeling"}:
        return
    template = ACTION_TEMPLATES[action.action_type]
    actor = working.npcs[action.actor_id]
    location_ref = actor.location_tile_id
    if action.target_tile_id:
        location_ref = action.target_tile_id
    elif action.target_settlement_id and action.target_settlement_id in working.settlements:
        location_ref = working.settlements[action.target_settlement_id].core_tile_id
    emit_info_packet(
        working,
        source_event_id=None,
        origin_actor_id=actor.id,
        content_domain="event",
        subject_ref=action.action_type,
        location_ref=location_ref,
        strength=max(10.0, template.visibility_strength * 0.55),
        visibility_scope="local",
        ttl=working.config.balance_parameters.rumor_base_ttl,
        truth_alignment=0.85,
        propagation_channels=["spatial", "relationship"],
    )


def _apply_success(working: WorldState, action: Action) -> None:
    actor = working.npcs[action.actor_id]
    if action.action_type == "FORAGE" and action.target_tile_id:
        tile = working.tiles[action.target_tile_id]
        amount = min(
            tile.current_stock.get("food", 0.0),
            tile.base_yield.get("food", 0.0) * working.config.balance_parameters.forage_yield_factor,
        )
        tile.current_stock["food"] -= amount
        actor.personal_inventory["food"] = actor.personal_inventory.get("food", 0.0) + amount
        emit_info_packet(
            working,
            source_event_id=None,
            origin_actor_id=actor.id,
            content_domain="resource",
            subject_ref=actor.id,
            location_ref=tile.id,
            strength=amount * 10.0,
            visibility_scope="local",
            ttl=working.config.balance_parameters.rumor_base_ttl,
            truth_alignment=1.0,
            propagation_channels=["spatial"],
        )
    elif action.action_type == "MOVE" and action.target_tile_id:
        move_npc_to_tile(working, actor.id, action.target_tile_id)
    elif action.action_type == "SCOUT" and action.target_tile_id:
        tile = working.tiles[action.target_tile_id]
        emit_info_packet(
            working,
            source_event_id=None,
            origin_actor_id=actor.id,
            content_domain="resource",
            subject_ref=action.target_tile_id,
            location_ref=action.target_tile_id,
            strength=tile.current_stock.get("food", 0.0) + tile.base_yield.get("food", 0.0) * 8.0,
            visibility_scope="local",
            ttl=working.config.balance_parameters.rumor_base_ttl,
            truth_alignment=0.95,
            propagation_channels=["relationship", "spatial"],
        )
    elif action.action_type == "TRADE" and action.target_settlement_id and actor.settlement_id:
        source_settlement = working.settlements.get(actor.settlement_id)
        target_settlement = working.settlements.get(action.target_settlement_id)
        if source_settlement and target_settlement:
            shipped_food = min(2.0, source_settlement.stored_resources.get("food", 0.0))
            source_settlement.stored_resources["food"] = source_settlement.stored_resources.get("food", 0.0) - shipped_food
            source_settlement.stored_resources["wealth"] = source_settlement.stored_resources.get("wealth", 0.0) + 0.8
            target_settlement.stored_resources["food"] = target_settlement.stored_resources.get("food", 0.0) + shipped_food
            target_settlement.stored_resources["wealth"] = target_settlement.stored_resources.get("wealth", 0.0) + 0.4
            if target_settlement.resident_npc_ids:
                counterpart_id = target_settlement.resident_npc_ids[0]
                apply_relation_template_between(working, actor.id, counterpart_id, "shared_work", reciprocal="shared_work")
    elif action.action_type == "MIGRATE" and action.target_tile_id:
        move_npc_to_tile(working, actor.id, action.target_tile_id)
        destination_settlement = working.tiles[action.target_tile_id].settlement_id
        if destination_settlement != actor.settlement_id:
            assign_npc_settlement(working, actor.id, destination_settlement)
    elif action.action_type == "FOUND_POLITY" and action.target_settlement_id:
        _found_polity(working, actor.id, action.target_settlement_id)
    elif action.action_type == "FORMAL_TAX_ORDER" and action.target_settlement_id:
        emit_command_packet(working, actor.id, action.target_settlement_id, "formal_tax_order")
    elif action.action_type == "LEVY_RESOURCES" and action.target_settlement_id:
        emit_command_packet(working, actor.id, action.target_settlement_id, "resource_levy")
    elif action.action_type == "DECLARE_WAR" and action.target_polity_id and actor.polity_id:
        _declare_war(working, actor.polity_id, action.target_polity_id)
    elif action.action_type == "MUSTER_FORCE" and action.target_settlement_id:
        emit_command_packet(working, actor.id, action.target_settlement_id, "muster_force")
    elif action.action_type == "SUPPRESS_UNREST" and action.target_settlement_id:
        emit_command_packet(working, actor.id, action.target_settlement_id, "suppress_unrest")


def _found_polity(working: WorldState, actor_id: str, settlement_id: str) -> None:
    actor = working.npcs[actor_id]
    if actor.faction_id is None:
        return
    settlement = working.settlements[settlement_id]
    faction = working.factions[actor.faction_id]
    polity_id = working.next_id("polity")
    working.polities[polity_id] = Polity(
        id=polity_id,
        name=f"{settlement.name} Polity",
        capital_settlement_id=settlement.id,
        ruling_faction_id=faction.id,
        ruler_npc_id=actor.id,
        member_settlement_ids=[],
        member_faction_ids=[faction.id],
        treasury={"food": 0.0, "wood": 0.0, "ore": 0.0, "wealth": 2.0},
        administrative_reach=55.0,
        legitimacy_components={"support": faction.support_score, "cohesion": faction.cohesion},
        stability=60.0,
        military_strength_base=25.0,
        external_relations={},
        active_modifier_ids=[],
        command_network_state={"integrity": 60.0, "latency": 20.0},
    )
    assign_settlement_polity(working, settlement.id, polity_id)
    for npc in working.npcs.values():
        if npc.settlement_id == settlement.id:
            assign_npc_polity(working, npc.id, polity_id)
    emit_info_packet(
        working,
        source_event_id=None,
        origin_actor_id=actor.id,
        content_domain="belief",
        subject_ref=polity_id,
        location_ref=settlement.core_tile_id,
        strength=70.0,
        visibility_scope="broad",
        ttl=3,
        truth_alignment=1.0,
        propagation_channels=["spatial", "relationship", "organizational"],
    )


def _declare_war(working: WorldState, attacker_polity_id: str, defender_polity_id: str) -> None:
    war_id = working.next_id("war")
    working.war_states[war_id] = WarState(
        id=war_id,
        participant_polity_ids=[attacker_polity_id, defender_polity_id],
        participant_faction_ids=[],
        start_step=working.current_step,
        war_type="formal",
        front_regions=[],
        war_support_levels={attacker_polity_id: 60.0, defender_polity_id: 55.0},
        war_fatigue_levels={attacker_polity_id: 5.0, defender_polity_id: 5.0},
        mobilization_modifiers=[],
        tax_modifiers=[],
        propagation_modifiers=[],
        legitimacy_effect_direction=-6.0,
        status="active",
    )


def _cleanup_and_hooks(working: WorldState) -> None:
    for action in working.action_queue:
        if action.status == ActionStatus.DECLARED.value and action.estimated_duration > 1:
            action.estimated_duration -= 1
    active_ids = {action.id for action in working.action_queue if action.status == ActionStatus.DECLARED.value}
    for npc in working.npcs.values():
        if npc.current_action_ref and npc.current_action_ref not in active_ids:
            npc.current_action_ref = None
    working.action_queue = [
        action for action in working.action_queue if action.status == ActionStatus.DECLARED.value
    ]


def run_political_phase(snapshot: WorldState, working: WorldState) -> None:
    _update_taxation(working)
    _execute_command_chain(working)
    _update_war_states(working)
    _update_settlement_hysteresis(working)
    _update_faction_hysteresis(working)
    _update_polity_hysteresis(working)
    reconcile_references(working)
    for error in validate_reference_consistency(working):
        working.log_error(error)


def _archive_settlement(world: WorldState, settlement_id: str) -> None:
    settlement = world.settlements[settlement_id]
    if settlement.faction_id and settlement.faction_id in world.factions:
        faction = world.factions[settlement.faction_id]
        if settlement_id in faction.settlement_ids:
            faction.settlement_ids.remove(settlement_id)
    if settlement.polity_id and settlement.polity_id in world.polities:
        polity = world.polities[settlement.polity_id]
        if settlement_id in polity.member_settlement_ids:
            polity.member_settlement_ids.remove(settlement_id)
    settlement = world.settlements.pop(settlement_id)
    world.archived_settlements[settlement_id] = settlement
    world.record_archived_state(settlement_id, "archived")


def _archive_faction(world: WorldState, faction_id: str) -> None:
    for polity in world.polities.values():
        if faction_id in polity.member_faction_ids:
            polity.member_faction_ids.remove(faction_id)
    faction = world.factions.pop(faction_id)
    world.archived_factions[faction_id] = faction
    world.record_archived_state(faction_id, "archived")


def _archive_polity(world: WorldState, polity_id: str) -> None:
    polity = world.polities.pop(polity_id)
    world.archived_polities[polity_id] = polity
    world.record_dissolved_state(polity_id, "dissolved")


def _execute_command_chain(world: WorldState) -> None:
    packet_deliveries: dict[str, list[str]] = world.history_index["packet_deliveries"]  # type: ignore[assignment]
    executed_packets: set[str] = world.history_index["executed_command_packets"]  # type: ignore[assignment]
    command_subjects: dict[str, str] = world.history_index["command_packet_subjects"]  # type: ignore[assignment]
    command_execution_log: list[dict[str, object]] = world.history_index["command_execution_log"]  # type: ignore[assignment]
    local_command_log: list[dict[str, object]] = world.history_index["local_command_log"]  # type: ignore[assignment]
    resource_flow_log: list[dict[str, object]] = world.history_index["resource_flow_log"]  # type: ignore[assignment]
    command_consequence_log: list[dict[str, object]] = world.history_index["command_consequence_log"]  # type: ignore[assignment]
    legitimacy_log: list[dict[str, object]] = world.history_index["legitimacy_log"]  # type: ignore[assignment]
    params = world.config.balance_parameters
    for packet in world.info_packets:
        if packet.content_domain != "command" or packet.id in executed_packets:
            continue
        if packet.subject_ref not in world.settlements:
            continue
        settlement = world.settlements[packet.subject_ref]
        origin = world.npcs.get(packet.origin_actor_id) if packet.origin_actor_id else None
        if origin is None or origin.polity_id is None or settlement.polity_id != origin.polity_id:
            continue
        delivered_npcs = packet_deliveries.get(packet.id, [])
        local_executors = [
            npc_id
            for npc_id in delivered_npcs
            if npc_id in world.npcs
            and world.npcs[npc_id].settlement_id == settlement.id
            and world.npcs[npc_id].polity_id == origin.polity_id
        ]
        command_subject = command_subjects.get(packet.id, "formal_tax_order")
        if not local_executors:
            polity = world.polities[origin.polity_id]
            polity.command_network_state["latency"] = min(100.0, polity.command_network_state.get("latency", 0.0) + 6.0)
            command_execution_log.append(
                {
                    "step": world.current_step,
                    "packet_id": packet.id,
                    "settlement_id": settlement.id,
                    "command_subject": command_subject,
                    "outcome": "delayed_no_executor",
                    "score": 0.0,
                }
            )
            continue
        polity = world.polities[origin.polity_id]
        primary_executor_id = max(
            local_executors,
            key=lambda npc_id: _executor_alignment_score(world, npc_id, polity, settlement),
        )
        capital_tile_id = world.settlements[polity.capital_settlement_id].core_tile_id
        distance_cost = shortest_path_cost(world, capital_tile_id, settlement.core_tile_id)
        if distance_cost == float("inf"):
            continue
        network_integrity = polity.command_network_state.get("integrity", 50.0)
        local_resistance = 0.0
        if settlement.faction_id and settlement.faction_id != polity.ruling_faction_id:
            local_resistance = world.factions[settlement.faction_id].cohesion * 0.2
        latency_penalty = polity.command_network_state.get("latency", 0.0) * 0.25
        execution_score = network_integrity + settlement.stability - distance_cost * 6.0 - local_resistance - latency_penalty
        alignment = _executor_alignment_score(world, primary_executor_id, polity, settlement)
        mode, compliance, skim_rate = _translate_command_mode(world, command_subject, alignment, packet.distortion)
        local_command_log.append(
            {
                "step": world.current_step,
                "packet_id": packet.id,
                "executor_id": primary_executor_id,
                "settlement_id": settlement.id,
                "command_subject": command_subject,
                "mode": mode,
                "alignment": round(alignment, 2),
                "compliance": round(compliance, 2),
                "skim_rate": round(skim_rate, 2),
            }
        )
        outcome = "failed"
        if execution_score >= 55.0:
            if mode == "resist":
                polity.command_network_state["latency"] = min(100.0, polity.command_network_state.get("latency", 0.0) + 5.0)
                polity.command_network_state["integrity"] = world.clamp_metric(
                    polity.command_network_state.get("integrity", 0.0) - params.command_resistance_integrity_penalty
                )
                polity.legitimacy_components["civil_order"] = world.clamp_metric(
                    polity.legitimacy_components.get("civil_order", 50.0) - 3.0
                )
                settlement.stability = world.clamp_metric(settlement.stability - 1.0)
                command_consequence_log.append(
                    {
                        "step": world.current_step,
                        "packet_id": packet.id,
                        "settlement_id": settlement.id,
                        "polity_id": polity.id,
                        "kind": "resistance",
                        "integrity_delta": round(-params.command_resistance_integrity_penalty, 2),
                        "civil_order_delta": -3.0,
                        "settlement_stability_delta": -1.0,
                    }
                )
                legitimacy_log.append(
                    {
                        "step": world.current_step,
                        "polity_id": polity.id,
                        "kind": "command_resistance",
                        "delta": -3.0,
                    }
                )
                outcome = "resisted"
            elif command_subject == "formal_tax_order":
                target_value = settlement.current_taxable_output * max(0.15, min(0.65, execution_score / 100.0)) * compliance
                extracted_bundle, _ = _extract_value_bundle(settlement.stored_resources, target_value)
                leakage = max(0.0, 1.0 - polity.administrative_reach / 100.0)
                remitted_rate = max(0.0, (1.0 - leakage) * (1.0 - skim_rate))
                remitted_bundle = _scaled_bundle(extracted_bundle, remitted_rate)
                retained_bundle = _scaled_bundle(extracted_bundle, 1.0 - remitted_rate)
                _merge_resource_bundle(polity.treasury, extracted_bundle, remitted_rate)
                _merge_resource_bundle(settlement.stored_resources, extracted_bundle, 1.0 - remitted_rate)
                polity.tax_leakage_rate = leakage
                resource_flow_log.append(
                    {
                        "step": world.current_step,
                        "flow_type": "tax_command",
                        "packet_id": packet.id,
                        "settlement_id": settlement.id,
                        "polity_id": polity.id,
                        "command_subject": command_subject,
                        "mode": mode,
                        "extracted_bundle": _rounded_bundle(extracted_bundle),
                        "remitted_bundle": _rounded_bundle(remitted_bundle),
                        "retained_bundle": _rounded_bundle(retained_bundle),
                        "extracted_value": round(_bundle_value(extracted_bundle), 2),
                        "remitted_value": round(_bundle_value(remitted_bundle), 2),
                        "retained_value": round(_bundle_value(retained_bundle), 2),
                    }
                )
                for npc_id in local_executors[:3]:
                    apply_relation_template_between(world, npc_id, polity.ruler_npc_id, "extractive_taxation")
                if skim_rate > 0.0:
                    integrity_delta = -skim_rate * params.command_skimming_integrity_penalty
                    civil_order_delta = -skim_rate * params.command_skimming_civil_order_penalty
                    stability_delta = skim_rate * params.command_local_retention_stability_gain
                    polity.command_network_state["integrity"] = world.clamp_metric(
                        polity.command_network_state.get("integrity", 0.0) + integrity_delta
                    )
                    polity.legitimacy_components["civil_order"] = world.clamp_metric(
                        polity.legitimacy_components.get("civil_order", 50.0) + civil_order_delta
                    )
                    settlement.stability = world.clamp_metric(settlement.stability + stability_delta)
                    command_consequence_log.append(
                        {
                            "step": world.current_step,
                            "packet_id": packet.id,
                            "settlement_id": settlement.id,
                            "polity_id": polity.id,
                            "kind": "skimming",
                            "integrity_delta": round(integrity_delta, 2),
                            "civil_order_delta": round(civil_order_delta, 2),
                            "settlement_stability_delta": round(stability_delta, 2),
                        }
                    )
                    legitimacy_log.append(
                        {
                            "step": world.current_step,
                            "polity_id": polity.id,
                            "kind": "command_skimming",
                            "delta": round(civil_order_delta, 2),
                        }
                    )
                else:
                    civil_order_delta = remitted_rate * params.command_compliance_civil_order_gain
                    polity.legitimacy_components["civil_order"] = world.clamp_metric(
                        polity.legitimacy_components.get("civil_order", 50.0) + civil_order_delta
                    )
                    command_consequence_log.append(
                        {
                            "step": world.current_step,
                            "packet_id": packet.id,
                            "settlement_id": settlement.id,
                            "polity_id": polity.id,
                            "kind": "compliance",
                            "integrity_delta": 0.0,
                            "civil_order_delta": round(civil_order_delta, 2),
                            "settlement_stability_delta": 0.0,
                        }
                    )
                    legitimacy_log.append(
                        {
                            "step": world.current_step,
                            "polity_id": polity.id,
                            "kind": "command_compliance",
                            "delta": round(civil_order_delta, 2),
                        }
                    )
                outcome = "executed_with_skimming" if skim_rate > 0.0 else "executed"
            elif command_subject == "resource_levy":
                levy_bundle = {}
                for resource in ("food", "wood", "ore"):
                    extracted = settlement.stored_resources.get(resource, 0.0) * 0.15 * compliance
                    settlement.stored_resources[resource] = settlement.stored_resources.get(resource, 0.0) - extracted
                    levy_bundle[resource] = extracted
                remitted_bundle = _scaled_bundle(levy_bundle, 1.0 - skim_rate)
                retained_bundle = _scaled_bundle(levy_bundle, skim_rate)
                _merge_resource_bundle(polity.treasury, levy_bundle, 1.0 - skim_rate)
                _merge_resource_bundle(settlement.stored_resources, levy_bundle, skim_rate)
                resource_flow_log.append(
                    {
                        "step": world.current_step,
                        "flow_type": "resource_levy",
                        "packet_id": packet.id,
                        "settlement_id": settlement.id,
                        "polity_id": polity.id,
                        "command_subject": command_subject,
                        "mode": mode,
                        "extracted_bundle": _rounded_bundle(levy_bundle),
                        "remitted_bundle": _rounded_bundle(remitted_bundle),
                        "retained_bundle": _rounded_bundle(retained_bundle),
                        "extracted_value": round(_bundle_value(levy_bundle), 2),
                        "remitted_value": round(_bundle_value(remitted_bundle), 2),
                        "retained_value": round(_bundle_value(retained_bundle), 2),
                    }
                )
                for npc_id in local_executors[:3]:
                    apply_relation_template_between(world, npc_id, polity.ruler_npc_id, "extractive_taxation")
                if skim_rate > 0.0:
                    integrity_delta = -skim_rate * params.command_skimming_integrity_penalty * 0.8
                    civil_order_delta = -skim_rate * params.command_skimming_civil_order_penalty * 0.8
                    stability_delta = skim_rate * params.command_local_retention_stability_gain * 0.8
                    polity.command_network_state["integrity"] = world.clamp_metric(
                        polity.command_network_state.get("integrity", 0.0) + integrity_delta
                    )
                    polity.legitimacy_components["civil_order"] = world.clamp_metric(
                        polity.legitimacy_components.get("civil_order", 50.0) + civil_order_delta
                    )
                    settlement.stability = world.clamp_metric(settlement.stability + stability_delta)
                    command_consequence_log.append(
                        {
                            "step": world.current_step,
                            "packet_id": packet.id,
                            "settlement_id": settlement.id,
                            "polity_id": polity.id,
                            "kind": "skimming",
                            "integrity_delta": round(integrity_delta, 2),
                            "civil_order_delta": round(civil_order_delta, 2),
                            "settlement_stability_delta": round(stability_delta, 2),
                        }
                    )
                    legitimacy_log.append(
                        {
                            "step": world.current_step,
                            "polity_id": polity.id,
                            "kind": "command_skimming",
                            "delta": round(civil_order_delta, 2),
                        }
                    )
                outcome = "executed_with_skimming" if skim_rate > 0.0 else "executed"
            elif command_subject == "muster_force":
                profile = _settlement_population_profile(world, settlement.id)
                combat_draw = max(0.0, min(profile["combat"] * 0.15, 2.0)) * compliance
                settlement.stored_resources["food"] = max(0.0, settlement.stored_resources.get("food", 0.0) - combat_draw * 0.8)
                polity.military_strength_base = world.clamp_metric(polity.military_strength_base + combat_draw * 4.0)
                polity.war_readiness = world.clamp_metric(polity.war_readiness + combat_draw * 8.0)
                resource_flow_log.append(
                    {
                        "step": world.current_step,
                        "flow_type": "muster_force",
                        "packet_id": packet.id,
                        "settlement_id": settlement.id,
                        "polity_id": polity.id,
                        "command_subject": command_subject,
                        "mode": mode,
                        "combat_draw": round(combat_draw, 2),
                        "food_cost": round(combat_draw * 0.8, 2),
                    }
                )
                for npc_id in local_executors[:3]:
                    apply_relation_template_between(world, npc_id, polity.ruler_npc_id, "repression")
                outcome = "softened" if mode == "soften" else "executed"
            elif command_subject == "suppress_unrest":
                security_gain = 10.0 * compliance
                stability_gain = 4.0 * compliance
                if mode == "soften":
                    security_gain *= 0.65
                    stability_gain *= 0.75
                settlement.security_level = world.clamp_metric(settlement.security_level + security_gain)
                settlement.stability = world.clamp_metric(settlement.stability + stability_gain)
                command_consequence_log.append(
                    {
                        "step": world.current_step,
                        "packet_id": packet.id,
                        "settlement_id": settlement.id,
                        "polity_id": polity.id,
                        "kind": "order_enforced",
                        "integrity_delta": 0.0,
                        "civil_order_delta": 0.0,
                        "settlement_stability_delta": round(stability_gain, 2),
                    }
                )
                for npc_id in local_executors[:3]:
                    apply_relation_template_between(world, npc_id, polity.ruler_npc_id, "repression")
                emit_info_packet(
                    world,
                    source_event_id=None,
                    origin_actor_id=polity.ruler_npc_id,
                    content_domain="relations",
                    subject_ref=settlement.id,
                    location_ref=settlement.core_tile_id,
                    strength=32.0,
                    visibility_scope="local",
                    ttl=world.config.balance_parameters.rumor_base_ttl,
                    truth_alignment=0.9,
                    propagation_channels=["spatial", "organizational"],
                )
                outcome = "softened" if mode == "soften" else "executed"
            if outcome != "resisted":
                polity.command_network_state["latency"] = max(0.0, polity.command_network_state.get("latency", 0.0) - 2.0)
            executed_packets.add(packet.id)
        elif execution_score >= 40.0:
            packet.distortion = min(1.0, packet.distortion + 0.12)
            polity.command_network_state["latency"] = min(100.0, polity.command_network_state.get("latency", 0.0) + 4.0)
            outcome = "delayed_distorted"
        else:
            packet.distortion = min(1.0, packet.distortion + 0.2)
            polity.command_network_state["latency"] = min(100.0, polity.command_network_state.get("latency", 0.0) + 6.0)
            settlement.stability = world.clamp_metric(settlement.stability - 1.5)
            outcome = "resisted"
        command_execution_log.append(
            {
                "step": world.current_step,
                "packet_id": packet.id,
                "settlement_id": settlement.id,
                "executor_id": primary_executor_id,
                "command_subject": command_subject,
                "outcome": outcome,
                "score": round(execution_score, 2),
                "mode": mode,
                "compliance": round(compliance, 2),
            }
        )


def _update_taxation(world: WorldState) -> None:
    active_war_fatigue: dict[str, float] = {}
    resource_flow_log: list[dict[str, object]] = world.history_index["resource_flow_log"]  # type: ignore[assignment]
    for war in world.war_states.values():
        if war.status != "active":
            continue
        for polity_id, fatigue in war.war_fatigue_levels.items():
            active_war_fatigue[polity_id] = max(active_war_fatigue.get(polity_id, 0.0), fatigue)
    for settlement in world.settlements.values():
        settlement.current_taxable_output = 0.0
        profile = _settlement_population_profile(world, settlement.id)
        labor_ratio = profile["labor"] / max(1.0, profile["total"])
        produced = (
            settlement.stored_resources.get("food", 0.0) * 0.2 * labor_ratio
            + settlement.stored_resources.get("wood", 0.0) * 0.15 * labor_ratio
            + settlement.stored_resources.get("ore", 0.0) * 0.25 * labor_ratio
            + settlement.stored_resources.get("wealth", 0.0)
        )
        settlement.current_taxable_output = produced
        if settlement.polity_id and settlement.polity_id in world.polities:
            polity = world.polities[settlement.polity_id]
            distance_cost = shortest_path_cost(
                world,
                world.settlements[polity.capital_settlement_id].core_tile_id,
                settlement.core_tile_id,
            )
            war_penalty = active_war_fatigue.get(polity.id, 0.0) * 0.15
            polity.administrative_reach = world.clamp_metric(70.0 - distance_cost * 4.0 - war_penalty)
            resource_flow_log.append(
                {
                    "step": world.current_step,
                    "flow_type": "tax_base",
                    "settlement_id": settlement.id,
                    "polity_id": polity.id,
                    "labor_ratio": round(labor_ratio, 2),
                    "taxable_output": round(produced, 2),
                    "administrative_reach": round(polity.administrative_reach, 2),
                }
            )


def _update_war_states(world: WorldState) -> None:
    war_log: list[dict[str, object]] = world.history_index["war_log"]  # type: ignore[assignment]
    legitimacy_log: list[dict[str, object]] = world.history_index["legitimacy_log"]  # type: ignore[assignment]
    loot_remittance_log: list[dict[str, object]] = world.history_index["loot_remittance_log"]  # type: ignore[assignment]
    resource_flow_log: list[dict[str, object]] = world.history_index["resource_flow_log"]  # type: ignore[assignment]
    active_participants: set[str] = set()
    for war in world.war_states.values():
        if war.status != "active":
            continue
        active_participants.update(war.participant_polity_ids)
        participants = [world.polities[polity_id] for polity_id in war.participant_polity_ids if polity_id in world.polities]
        if len(participants) < 2:
            war.status = "ended"
            continue
        attacker, defender = participants[0], participants[1]
        attacker_profile = _polity_population_profile(world, attacker.id)
        defender_profile = _polity_population_profile(world, defender.id)
        attacker_strength = attacker.military_strength_base + attacker.war_readiness * 0.4 + attacker_profile["combat"] * 2.0
        defender_strength = defender.military_strength_base + defender.war_readiness * 0.4 + defender_profile["combat"] * 2.0
        capital_distance = shortest_path_cost(
            world,
            world.settlements[attacker.capital_settlement_id].core_tile_id,
            world.settlements[defender.capital_settlement_id].core_tile_id,
        )
        if capital_distance == float("inf"):
            capital_distance = 12.0
        average_strength = (attacker_strength + defender_strength) / 2.0
        war.effective_front_pressure = max(5.0, average_strength * 0.08 - capital_distance)
        war.expected_attrition = max(1.0, world.config.balance_parameters.war_attrition_scale * average_strength * 0.1)
        war.escalation_risk = min(100.0, war.effective_front_pressure + sum(war.war_fatigue_levels.values()) * 0.25)
        winner = attacker if attacker_strength >= defender_strength else defender
        loser = defender if winner is attacker else attacker
        loot = min(loser.treasury.get("wealth", 0.0), world.config.balance_parameters.war_loot_rate * max(1.0, war.effective_front_pressure))
        loser.treasury["wealth"] = max(0.0, loser.treasury.get("wealth", 0.0) - loot)
        winner_capital = world.settlements[winner.capital_settlement_id]
        winner_capital.stored_resources["wealth"] = winner_capital.stored_resources.get("wealth", 0.0) + loot
        winner_capital.stored_resources["food"] = winner_capital.stored_resources.get("food", 0.0) + loot * 0.2
        resource_flow_log.append(
            {
                "step": world.current_step,
                "flow_type": "war_loot_capture",
                "war_id": war.id,
                "settlement_id": winner_capital.id,
                "polity_id": winner.id,
                "captured_bundle": {"wealth": round(loot, 2), "food": round(loot * 0.2, 2)},
                "captured_value": round(loot * 1.2, 2),
            }
        )
        remitted = loot * world.config.balance_parameters.loot_remittance_rate * max(0.2, winner.administrative_reach / 100.0)
        winner_capital.stored_resources["wealth"] = max(0.0, winner_capital.stored_resources.get("wealth", 0.0) - remitted)
        winner.treasury["wealth"] = winner.treasury.get("wealth", 0.0) + remitted
        resource_flow_log.append(
            {
                "step": world.current_step,
                "flow_type": "war_loot_remittance",
                "war_id": war.id,
                "settlement_id": winner_capital.id,
                "polity_id": winner.id,
                "remitted_bundle": {"wealth": round(remitted, 2)},
                "retained_bundle": {"wealth": round(max(0.0, loot - remitted), 2), "food": round(loot * 0.2, 2)},
                "remitted_value": round(remitted, 2),
            }
        )
        loot_remittance_log.append(
            {
                "step": world.current_step,
                "war_id": war.id,
                "winner_polity_id": winner.id,
                "winner_settlement_id": winner_capital.id,
                "captured_loot": round(loot, 2),
                "remitted_loot": round(remitted, 2),
            }
        )
        for polity, profile in ((attacker, attacker_profile), (defender, defender_profile)):
            fatigue_gain = 1.5 + war.expected_attrition + max(0.0, 12.0 - capital_distance) * 0.1
            war.war_fatigue_levels[polity.id] = min(100.0, war.war_fatigue_levels.get(polity.id, 0.0) + fatigue_gain)
            polity.stability = world.clamp_metric(polity.stability - (1.0 + war.expected_attrition * 0.4))
            polity.legitimacy_components["war_strain"] = polity.legitimacy_components.get("war_strain", 0.0) + fatigue_gain
            polity.legitimacy_components["civil_order"] = world.clamp_metric(
                polity.legitimacy_components.get("civil_order", 50.0) - fatigue_gain * 0.35
            )
            polity.treasury["food"] = max(0.0, polity.treasury.get("food", 0.0) - max(0.5, profile["combat"] * 0.1))
            polity.military_strength_base = world.clamp_metric(polity.military_strength_base - war.expected_attrition * 0.3)
            polity.frontier_tension = max(0.0, polity.frontier_tension - 1.0)
            legitimacy_log.append(
                {
                    "step": world.current_step,
                    "polity_id": polity.id,
                    "kind": "war_strain",
                    "delta": round(-fatigue_gain * 0.35, 2),
                }
            )
        war_log.append(
            {
                "step": world.current_step,
                "war_id": war.id,
                "winner_polity_id": winner.id,
                "loser_polity_id": loser.id,
                "loot": round(loot, 2),
                "front_pressure": round(war.effective_front_pressure, 2),
            }
        )
    for polity in world.polities.values():
        if polity.id in active_participants:
            continue
        polity.frontier_tension = world.clamp_metric(polity.frontier_tension + world.config.balance_parameters.peace_tension_gain)
        polity.legitimacy_components["war_strain"] = max(
            0.0,
            polity.legitimacy_components.get("war_strain", 0.0) - world.config.balance_parameters.war_strain_decay,
        )
        if polity.frontier_tension >= 40.0:
            polity.stability = world.clamp_metric(polity.stability - 0.3)
            legitimacy_log.append(
                {
                    "step": world.current_step,
                    "polity_id": polity.id,
                    "kind": "peace_tension",
                    "delta": -0.3,
                }
            )


def _update_settlement_hysteresis(world: WorldState) -> None:
    entry_threshold = world.config.balance_parameters.local_settlement_entry_population
    exit_threshold = world.config.balance_parameters.local_settlement_exit_population
    grouped: dict[str, list[str]] = defaultdict(list)
    for npc in world.npcs.values():
        if npc.alive:
            grouped[npc.location_tile_id].append(npc.id)
    for tile_id, residents in grouped.items():
        tile = world.tiles[tile_id]
        if tile.settlement_id is None and len(residents) >= entry_threshold:
            settlement_id = world.next_id("settlement")
            world.settlements[settlement_id] = Settlement(
                id=settlement_id,
                name=f"Settlement {settlement_id.split(':')[-1]}",
                core_tile_id=tile_id,
                member_tile_ids=[tile_id],
                resident_npc_ids=[],
                stored_resources={"food": 6.0, "wood": 2.0, "ore": 0.0, "wealth": 0.0},
                security_level=45.0,
                stability=48.0,
                faction_id=None,
                polity_id=None,
                active_modifier_ids=[],
                labor_pool=float(len(residents)),
            )
            tile.settlement_id = settlement_id
            for npc_id in residents:
                assign_npc_settlement(world, npc_id, settlement_id)
    for settlement_id, settlement in list(world.settlements.items()):
        living_residents = [npc_id for npc_id in settlement.resident_npc_ids if world.npcs[npc_id].alive]
        if len(living_residents) <= exit_threshold:
            for npc_id in list(settlement.resident_npc_ids):
                assign_npc_settlement(world, npc_id, None)
            _archive_settlement(world, settlement_id)


def _update_faction_hysteresis(world: WorldState) -> None:
    entry = world.config.balance_parameters.faction_entry_support
    exit = world.config.balance_parameters.faction_exit_support
    for settlement in list(world.settlements.values()):
        if settlement.faction_id is None and settlement.stability >= entry and len(settlement.resident_npc_ids) >= 3:
            leader_id = max(settlement.resident_npc_ids, key=lambda npc_id: world.npcs[npc_id].office_rank)
            faction_id = world.next_id("faction")
            world.factions[faction_id] = Faction(
                id=faction_id,
                name=f"Faction {faction_id.split(':')[-1]}",
                leader_npc_id=leader_id,
                member_npc_ids=[],
                settlement_ids=[],
                support_score=60.0,
                cohesion=58.0,
                agenda_type="growth",
                legitimacy_seed_components={"support": 60.0},
                active_modifier_ids=[],
            )
            for npc_id in settlement.resident_npc_ids[:3]:
                assign_npc_faction(world, npc_id, faction_id)
            assign_settlement_faction(world, settlement.id, faction_id)
        elif settlement.faction_id:
            faction = world.factions.get(settlement.faction_id)
            if faction and (faction.support_score < exit or faction.cohesion < exit):
                for npc_id in list(faction.member_npc_ids):
                    assign_npc_faction(world, npc_id, None)
                _archive_faction(world, faction.id)
                settlement.faction_id = None


def _update_polity_hysteresis(world: WorldState) -> None:
    for polity_id, polity in list(world.polities.items()):
        if (
            polity.stability < world.config.balance_parameters.polity_exit_stability
            or polity.administrative_reach < world.config.balance_parameters.polity_entry_reach * 0.5
        ):
            for settlement_id in list(polity.member_settlement_ids):
                if settlement_id in world.settlements:
                    assign_settlement_polity(world, settlement_id, None)
            for npc in world.npcs.values():
                if npc.polity_id == polity_id:
                    assign_npc_polity(world, npc.id, None)
            _archive_polity(world, polity_id)


def run_event_phase(snapshot: WorldState, working: WorldState) -> None:
    materialize_outcomes(working)
    _update_objectives(working)


def _update_objectives(world: WorldState) -> None:
    for objective in world.player_state.active_objectives:
        if objective.objective_type == "POLITY_COUNT":
            objective.progress = float(len(world.polities))
        elif objective.objective_type == "SETTLEMENT_COUNT":
            objective.progress = float(len(world.settlements))
        objective.completed = objective.progress >= objective.threshold
        objective.maintained_steps = objective.maintained_steps + 1 if objective.completed else 0
        if any(condition == "no_polity" and not world.polities for condition in objective.failure_conditions):
            objective.failed = True


def _activate_delayed_effects(world: WorldState) -> None:
    remaining_queue = []
    for effect in world.delayed_effect_queue:
        if effect["activation_step"] > world.current_step:
            remaining_queue.append(effect)
            continue
        channel = effect["channel"]
        if channel == "modifier":
            modifier_id = world.next_id("modifier")
            from coma_engine.models.entities import Modifier

            world.modifiers[modifier_id] = Modifier(
                id=modifier_id,
                modifier_type=str(effect["modifier_type"]),
                mode="additive",
                target_ref=str(effect["target_ref"]),
                domain=str(effect["domain"]),
                magnitude=float(effect["magnitude"]),
                duration_remaining=int(effect["duration"]),
                stacking_rule="stack",
                priority=10,
                source_ref=str(effect["source_ref"]),
                trigger_rule=None,
            )
        elif channel == "info_packet":
            emit_info_packet(
                world,
                source_event_id=None,
                origin_actor_id=None,
                content_domain=str(effect["content_domain"]),
                subject_ref=effect["subject_ref"],
                location_ref=effect["location_ref"],
                strength=float(effect["strength"]),
                visibility_scope="local",
                ttl=world.config.balance_parameters.rumor_base_ttl,
                truth_alignment=1.0,
                propagation_channels=["spatial", "relationship"],
            )
        elif channel == "event":
            event_id = world.next_id("event")
            from coma_engine.models.entities import Event

            world.events[event_id] = Event(
                id=event_id,
                event_type=str(effect["event_type"]),
                timestamp_step=world.current_step,
                location_tile_id=str(effect["location_ref"]),
                region_ref=None,
                participant_ids=list(effect["participant_ids"]),
                cause_refs=["player"],
                outcome_summary_code="player_intervention_event",
                importance=70.0,
                visibility_scope="local",
                derived_memory_ids=[],
                derived_modifier_ids=[],
                derived_info_packet_ids=[],
            )
    world.delayed_effect_queue = remaining_queue
