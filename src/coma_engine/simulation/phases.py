from __future__ import annotations

from collections import defaultdict

from coma_engine.actions.catalog import ACTION_TEMPLATES
from coma_engine.actions.models import Action, ActionOutcome, ContestScore
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
from coma_engine.models.entities import Faction, Polity, Settlement, WarState
from coma_engine.models.perception import (
    OpportunityPerception,
    PowerMapPerception,
    RecentEventPerception,
    ResourceSignalPerception,
    ThreatPerception,
)
from coma_engine.systems.events import materialize_outcomes
from coma_engine.systems.modifiers import active_modifiers_for, apply_modifier_pipeline, tick_modifier_lifecycles
from coma_engine.systems.propagation import emit_command_packet, emit_info_packet, propagate_info_packets
from coma_engine.systems.relations import compute_group_salience
from coma_engine.systems.spatial import shortest_path_cost, traversable_neighbors


def run_environment_phase(snapshot: WorldState, working: WorldState) -> None:
    _activate_delayed_effects(working)
    for tile in working.tiles.values():
        tile.current_stock["food"] = tile.current_stock.get("food", 0.0) + (
            tile.base_yield.get("food", 0.0) * working.config.balance_parameters.tile_regen_rate
        )
    tick_modifier_lifecycles(working)
    for packet in working.info_packets:
        packet.propagated_this_step = False


def run_resource_phase(snapshot: WorldState, working: WorldState) -> None:
    for settlement in working.settlements.values():
        settlement.net_production = {resource: 0.0 for resource in working.config.design_constants.resource_types}
        settlement.current_taxable_output = 0.0
        settlement.labor_pool = float(len(settlement.resident_npc_ids))
    for npc in working.npcs.values():
        if not npc.alive:
            continue
        tile = working.tiles[npc.location_tile_id]
        tile_modifiers = active_modifiers_for(working, tile.id, "yield.food")
        allowed, yield_value, _ = apply_modifier_pipeline(tile.base_yield.get("food", 0.0), tile_modifiers)
        tile.effective_yield["food"] = yield_value if allowed else 0.0
        if npc.settlement_id and npc.settlement_id in working.settlements:
            settlement = working.settlements[npc.settlement_id]
            produced = min(tile.current_stock.get("food", 0.0), tile.effective_yield["food"] * 0.5)
            tile.current_stock["food"] -= produced
            settlement.stored_resources["food"] = settlement.stored_resources.get("food", 0.0) + produced
            settlement.net_production["food"] += produced
        else:
            produced = min(tile.current_stock.get("food", 0.0), tile.effective_yield["food"] * 0.3)
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
    state.perceived_recent_events = state.perceived_recent_events[
        : world.config.balance_parameters.perception_channel_capacity
    ]


def _availability_for(world: WorldState, npc_id: str, action_type: str, target_ref: str | None) -> bool:
    npc = world.npcs[npc_id]
    if not npc.alive:
        return False
    if action_type == "FORAGE":
        return True
    if action_type == "MOVE":
        return target_ref is not None and target_ref in traversable_neighbors(world, npc.location_tile_id)
    if action_type == "FOUND_POLITY":
        if npc.office_rank < world.config.balance_parameters.low_rank_high_politics_gate_rank:
            return False
        if not npc.settlement_id or not npc.faction_id:
            return False
        settlement = world.settlements[npc.settlement_id]
        faction = world.factions[npc.faction_id]
        if settlement.polity_id:
            return False
        return (
            faction.support_score >= world.config.balance_parameters.polity_entry_support
            and faction.cohesion >= world.config.balance_parameters.polity_entry_support
            and settlement.stability >= world.config.balance_parameters.polity_entry_stability
        )
    if action_type == "FORMAL_TAX_ORDER":
        return npc.polity_id is not None and npc.office_rank >= 3
    if action_type == "DECLARE_WAR":
        return npc.polity_id is not None and npc.office_rank >= 4 and len(world.polities) > 1
    return False


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


def _score_action(world: WorldState, npc_id: str, action_type: str, target_ref: str | None) -> dict[str, float]:
    npc = world.npcs[npc_id]
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
    elif action_type == "FOUND_POLITY":
        scores["goal_progress"] = 60.0 if npc.long_term_goal.goal_type == "FOUND_POLITY" else 25.0
        scores["belief_consistency"] = npc.beliefs.get("destiny", 0.0) * 0.4
        scores["risk_penalty"] = 25.0
        scores["organization_conflict_cost"] = max(0.0, 50.0 - compute_group_salience(world, npc)["faction"])
    elif action_type == "FORMAL_TAX_ORDER":
        scores["goal_progress"] = 24.0
        scores["organization_conflict_cost"] = 10.0
    elif action_type == "DECLARE_WAR":
        scores["goal_progress"] = 18.0
        scores["risk_penalty"] = 30.0
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
        for adjacent_id in candidate_move_targets:
            action_space.append(("MOVE", adjacent_id))
        if npc.settlement_id:
            action_space.append(("FOUND_POLITY", npc.settlement_id))
            action_space.append(("FORMAL_TAX_ORDER", npc.settlement_id))
        if npc.polity_id:
            for polity_id in working.polities:
                if polity_id != npc.polity_id:
                    action_space.append(("DECLARE_WAR", polity_id))
                    break

        scored = []
        for action_type, target_ref in action_space:
            if not _availability_for(working, npc.id, action_type, target_ref):
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
                resource_cost={"food": 0.0, "wood": 0.0, "ore": 0.0, "wealth": 0.0},
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
        if action.id not in unique_ids and action.status == ActionStatus.DECLARED.value and _validate_action_signature(action):
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
    valid_actions = _validity_check(snapshot, declared)
    reserved_actions = _resource_reservation(working, valid_actions)
    resolved = _contest_resolution(working, reserved_actions)
    _effect_application(working, resolved)
    _cleanup_and_hooks(working)


def _validity_check(snapshot: WorldState, actions: list[Action]) -> list[Action]:
    return [action for action in actions if action.actor_id in snapshot.npcs and snapshot.npcs[action.actor_id].alive]


def _resource_reservation(working: WorldState, actions: list[Action]) -> list[Action]:
    reserved = []
    for action in actions:
        actor = working.npcs[action.actor_id]
        affordable = all(actor.personal_inventory.get(resource, 0.0) >= amount for resource, amount in action.resource_cost.items())
        if not affordable:
            continue
        for resource, amount in action.resource_cost.items():
            actor.personal_inventory[resource] = actor.personal_inventory.get(resource, 0.0) - amount
        action.status = ActionStatus.RESERVED.value
        reserved.append(action)
    return reserved


def _contest_resolution(working: WorldState, actions: list[Action]) -> list[tuple[Action, ContestScore, str]]:
    grouped: dict[str, list[Action]] = defaultdict(list)
    for action in actions:
        grouped[action.resolution_group_key].append(action)
    results: list[tuple[Action, ContestScore, str]] = []
    for group_actions in grouped.values():
        scored = []
        for action in group_actions:
            actor = working.npcs[action.actor_id]
            score = ContestScore(
                ability_component=actor.abilities.get("politics", 0.0) if action.action_type != "FORAGE" else actor.abilities.get("foraging", 0.0),
                support_component=10.0 if actor.faction_id else 0.0,
                position_component=5.0 if actor.settlement_id else 0.0,
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


def _effect_application(working: WorldState, resolved: list[tuple[Action, ContestScore, str]]) -> None:
    working.outcome_records = []
    for action, _score, result in resolved:
        outcome_result = result
        if result == "succeeded" and action.duration_type != "instant" and action.estimated_duration > 1:
            _emit_continuation_leak(working, action)
            action.status = ActionStatus.DECLARED.value
            outcome_result = "partial"
        elif result == "succeeded":
            _apply_success(working, action)
            action.status = ActionStatus.SUCCEEDED.value
        else:
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


def _emit_continuation_leak(working: WorldState, action: Action) -> None:
    if action.duration_type not in {"travel", "campaign", "scheme", "channeling"}:
        return
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
        strength=18.0,
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
    elif action.action_type == "FOUND_POLITY" and action.target_settlement_id:
        _found_polity(working, actor.id, action.target_settlement_id)
    elif action.action_type == "FORMAL_TAX_ORDER" and action.target_settlement_id:
        emit_command_packet(working, actor.id, action.target_settlement_id, "formal_tax_order")
    elif action.action_type == "DECLARE_WAR" and action.target_polity_id and actor.polity_id:
        _declare_war(working, actor.polity_id, action.target_polity_id)


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
    _execute_command_chain(working)
    _update_taxation(working)
    _update_war_states(working)
    _update_settlement_hysteresis(working)
    _update_faction_hysteresis(working)
    _update_polity_hysteresis(working)
    reconcile_references(working)
    for error in validate_reference_consistency(working):
        working.log_error(error)


def _archive_settlement(world: WorldState, settlement_id: str) -> None:
    settlement = world.settlements.pop(settlement_id)
    world.archived_settlements[settlement_id] = settlement
    world.record_archived_state(settlement_id, "archived")


def _archive_faction(world: WorldState, faction_id: str) -> None:
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
        if not local_executors:
            continue
        polity = world.polities[origin.polity_id]
        capital_tile_id = world.settlements[polity.capital_settlement_id].core_tile_id
        distance_cost = shortest_path_cost(world, capital_tile_id, settlement.core_tile_id)
        if distance_cost == float("inf"):
            continue
        network_integrity = polity.command_network_state.get("integrity", 50.0)
        local_resistance = 0.0
        if settlement.faction_id and settlement.faction_id != polity.ruling_faction_id:
            local_resistance = world.factions[settlement.faction_id].cohesion * 0.2
        execution_score = network_integrity + settlement.stability - distance_cost * 6.0 - local_resistance
        if execution_score >= 45.0:
            collected = settlement.current_taxable_output * max(0.15, min(0.65, execution_score / 100.0))
            leakage = max(0.0, 1.0 - polity.administrative_reach / 100.0)
            actual = collected * (1.0 - leakage)
            polity.treasury["wealth"] = polity.treasury.get("wealth", 0.0) + actual
            polity.tax_leakage_rate = leakage
            executed_packets.add(packet.id)
        else:
            polity.command_network_state["latency"] = min(100.0, polity.command_network_state.get("latency", 0.0) + 5.0)


def _update_taxation(world: WorldState) -> None:
    for settlement in world.settlements.values():
        settlement.current_taxable_output = 0.0
        produced = (
            settlement.stored_resources.get("food", 0.0) * 0.2
            + settlement.stored_resources.get("wood", 0.0) * 0.15
            + settlement.stored_resources.get("ore", 0.0) * 0.25
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
            polity.administrative_reach = world.clamp_metric(70.0 - distance_cost * 4.0)


def _update_war_states(world: WorldState) -> None:
    for war in world.war_states.values():
        if war.status != "active":
            continue
        participants = [world.polities[polity_id] for polity_id in war.participant_polity_ids if polity_id in world.polities]
        if len(participants) < 2:
            war.status = "ended"
            continue
        average_strength = sum(polity.military_strength_base for polity in participants) / len(participants)
        war.effective_front_pressure = average_strength * 0.1
        war.expected_attrition = 2.0 + len(participants)
        war.escalation_risk = min(100.0, war.effective_front_pressure + sum(war.war_fatigue_levels.values()) * 0.2)
        for polity in participants:
            war.war_fatigue_levels[polity.id] = min(100.0, war.war_fatigue_levels.get(polity.id, 0.0) + 2.0)
            polity.stability = world.clamp_metric(polity.stability - 1.5)
            polity.legitimacy_components["war_strain"] = polity.legitimacy_components.get("war_strain", 0.0) + 2.0
            polity.treasury["wealth"] = max(0.0, polity.treasury.get("wealth", 0.0) - 0.5)


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
