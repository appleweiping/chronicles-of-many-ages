from __future__ import annotations

from coma_engine.core.state import WorldState


def _need_label(value: float) -> str:
    if value >= 70.0:
        return "critical"
    if value >= 45.0:
        return "strained"
    if value >= 20.0:
        return "stable"
    return "secure"


def _trend_label(value: float) -> str:
    if value >= 65.0:
        return "high"
    if value >= 40.0:
        return "mixed"
    return "low"


def debug_grade_action_explanations(world: WorldState, step: int) -> dict[str, dict[str, float]]:
    explanations = world.history_index["action_explanations"]  # type: ignore[index]
    return explanations.get(step, {})  # type: ignore[return-value]


def debug_grade_step_report(world: WorldState, step: int) -> list[str]:
    lines: list[str] = []
    for npc_id, breakdown in debug_grade_action_explanations(world, step).items():
        ordered = ", ".join(f"{key}={value:.1f}" for key, value in breakdown.items())
        lines.append(f"{npc_id}: {ordered}")
    command_log: list[str] = world.history_index["command_log"]  # type: ignore[assignment]
    lines.extend(f"command:{entry}" for entry in command_log[-5:])
    command_execution_log: list[dict[str, object]] = world.history_index["command_execution_log"]  # type: ignore[assignment]
    for entry in command_execution_log[-5:]:
        lines.append(
            "command_exec:"
            f"{entry.get('packet_id')}:{entry.get('command_subject')}:"
            f"{entry.get('outcome')}:score={entry.get('score')}"
        )
    war_log: list[dict[str, object]] = world.history_index["war_log"]  # type: ignore[assignment]
    for entry in war_log[-3:]:
        lines.append(
            "war:"
            f"{entry.get('war_id')}:winner={entry.get('winner_polity_id')}:"
            f"loser={entry.get('loser_polity_id')}:loot={entry.get('loot')}"
        )
    legitimacy_log: list[dict[str, object]] = world.history_index["legitimacy_log"]  # type: ignore[assignment]
    for entry in legitimacy_log[-5:]:
        lines.append(
            "legitimacy:"
            f"{entry.get('polity_id')}:{entry.get('kind')}:delta={entry.get('delta')}"
        )
    demographic_log: list[dict[str, object]] = world.history_index["demographic_log"]  # type: ignore[assignment]
    for entry in demographic_log[-5:]:
        lines.append(
            "demography:"
            f"{entry.get('kind')}:{entry.get('npc_id')}:at={entry.get('location_ref')}"
        )
    relation_log: list[dict[str, object]] = world.history_index["relation_log"]  # type: ignore[assignment]
    for entry in relation_log[-5:]:
        lines.append(
            "relation:"
            f"{entry.get('source_id')}->{entry.get('target_id')}:"
            f"{entry.get('template')}:x{entry.get('scale')}"
        )
    local_command_log: list[dict[str, object]] = world.history_index["local_command_log"]  # type: ignore[assignment]
    for entry in local_command_log[-5:]:
        lines.append(
            "local_command:"
            f"{entry.get('executor_id')}:{entry.get('command_subject')}:"
            f"{entry.get('mode')}:compliance={entry.get('compliance')}"
        )
    resource_flow_log: list[dict[str, object]] = world.history_index["resource_flow_log"]  # type: ignore[assignment]
    for entry in resource_flow_log[-6:]:
        flow_type = entry.get("flow_type")
        if flow_type == "tax_base":
            lines.append(
                "resource_flow:"
                f"tax_base:{entry.get('settlement_id')}:taxable={entry.get('taxable_output')}:"
                f"reach={entry.get('administrative_reach')}"
            )
        elif flow_type in {"tax_command", "resource_levy"}:
            lines.append(
                "resource_flow:"
                f"{flow_type}:{entry.get('settlement_id')}:remitted={entry.get('remitted_value')}:"
                f"retained={entry.get('retained_value')}"
            )
        elif flow_type == "resource_allocation":
            lines.append(
                "resource_flow:"
                f"allocation:{entry.get('settlement_id')}:delivered={entry.get('delivered_value')}:"
                f"diverted={entry.get('diverted_value')}"
            )
        elif flow_type == "muster_force":
            lines.append(
                "resource_flow:"
                f"muster:{entry.get('settlement_id')}:combat_draw={entry.get('combat_draw')}:"
                f"food_cost={entry.get('food_cost')}"
            )
        elif flow_type == "war_loot_capture":
            lines.append(
                "resource_flow:"
                f"war_capture:{entry.get('settlement_id')}:value={entry.get('captured_value')}"
            )
        elif flow_type == "war_loot_remittance":
            lines.append(
                "resource_flow:"
                f"war_remit:{entry.get('settlement_id')}:remitted={entry.get('remitted_value')}"
            )
    command_consequence_log: list[dict[str, object]] = world.history_index["command_consequence_log"]  # type: ignore[assignment]
    for entry in command_consequence_log[-5:]:
        lines.append(
            "command_effect:"
            f"{entry.get('kind')}:{entry.get('settlement_id')}:"
            f"integrity={entry.get('integrity_delta')}:"
            f"civil_order={entry.get('civil_order_delta')}:"
            f"stability={entry.get('settlement_stability_delta')}"
        )
    belief_log: list[dict[str, object]] = world.history_index["belief_log"]  # type: ignore[assignment]
    for entry in belief_log[-5:]:
        lines.append(
            "belief:"
            f"{entry.get('npc_id')}:{entry.get('belief_domain')}:"
            f"{entry.get('source_event_id')}:strength={entry.get('strength')}"
        )
    memory_log: list[dict[str, object]] = world.history_index["memory_conversion_log"]  # type: ignore[assignment]
    for entry in memory_log[-5:]:
        lines.append(
            "memory_convert:"
            f"{entry.get('memory_id')}:{entry.get('npc_id')}:"
            f"{entry.get('belief_domain')}"
        )
    loot_log: list[dict[str, object]] = world.history_index["loot_remittance_log"]  # type: ignore[assignment]
    for entry in loot_log[-5:]:
        lines.append(
            "loot_remit:"
            f"{entry.get('war_id')}:{entry.get('winner_settlement_id')}:"
            f"captured={entry.get('captured_loot')}:remitted={entry.get('remitted_loot')}"
        )
    war_supply_log: list[dict[str, object]] = world.history_index["war_supply_log"]  # type: ignore[assignment]
    for entry in war_supply_log[-6:]:
        lines.append(
            "war_supply:"
            f"{entry.get('war_id')}:{entry.get('polity_id')}:{entry.get('kind')}:"
            f"value={entry.get('drawn_value')}:ratio={entry.get('supply_ratio')}"
        )
    war_command_log: list[dict[str, object]] = world.history_index["war_command_log"]  # type: ignore[assignment]
    for entry in war_command_log[-6:]:
        lines.append(
            "war_command:"
            f"{entry.get('war_id')}:{entry.get('polity_id')}:{entry.get('command_subject')}:"
            f"support={entry.get('support_delta')}:burden={entry.get('local_burden_delta')}"
        )
    return lines


def player_grade_recent_history(world: WorldState, limit: int = 5) -> list[str]:
    recent_events = sorted(world.events.values(), key=lambda event: (event.timestamp_step, event.id), reverse=True)
    return [
        f"Step {event.timestamp_step}: {event.event_type} ({event.outcome_summary_code})"
        for event in recent_events[:limit]
    ]


def player_grade_world_summary(world: WorldState) -> list[str]:
    return [
        f"Step: {world.current_step}",
        f"Active settlements: {len(world.settlements)}",
        f"Archived settlements: {len(world.archived_settlements)}",
        f"Active factions: {len(world.factions)}",
        f"Archived factions: {len(world.archived_factions)}",
        f"Active polities: {len(world.polities)}",
        f"Archived polities: {len(world.archived_polities)}",
        f"Active wars: {len([war for war in world.war_states.values() if war.status == 'active'])}",
        f"Events: {len(world.events)}",
    ]


def player_grade_npc_summary(world: WorldState, npc_id: str) -> list[str]:
    npc = world.npcs[npc_id]
    return [
        f"{npc.id} {npc.name}",
        f"role={npc.role} tile={npc.location_tile_id}",
        f"settlement={npc.settlement_id} faction={npc.faction_id} polity={npc.polity_id}",
        f"food_need={_need_label(npc.needs.get('food', 0.0))} safety_need={_need_label(npc.needs.get('safety', 0.0))}",
        f"health={_trend_label(npc.health)} office_rank={npc.office_rank}",
    ]


def player_grade_settlement_summary(world: WorldState, settlement_id: str) -> list[str]:
    settlement = world.entity_by_ref(settlement_id)
    if settlement is None:
        return [f"{settlement_id} not found"]
    resident_count = len(getattr(settlement, "resident_npc_ids", []))
    return [
        f"{settlement.id} {settlement.name}",
        f"residents={resident_count} polity={settlement.polity_id} faction={settlement.faction_id}",
        f"food={settlement.stored_resources.get('food', 0.0):.1f} wood={settlement.stored_resources.get('wood', 0.0):.1f} ore={settlement.stored_resources.get('ore', 0.0):.1f} wealth={settlement.stored_resources.get('wealth', 0.0):.1f}",
        f"taxable_output={settlement.current_taxable_output:.1f} labor_pool={settlement.labor_pool:.1f}",
        f"stability={_trend_label(settlement.stability)} security={_trend_label(settlement.security_level)}",
    ]


def player_grade_polity_summary(world: WorldState, polity_id: str) -> list[str]:
    polity = world.entity_by_ref(polity_id)
    if polity is None:
        return [f"{polity_id} not found"]
    legitimacy = polity.legitimacy_components
    return [
        f"{polity.id} {polity.name}",
        f"capital={polity.capital_settlement_id} ruler={polity.ruler_npc_id}",
        f"stability={_trend_label(polity.stability)} reach={_trend_label(polity.administrative_reach)} war_readiness={_trend_label(polity.war_readiness)}",
        f"legitimacy_support={_trend_label(legitimacy.get('support', 0.0))} civil_order={_trend_label(legitimacy.get('civil_order', 50.0))}",
        f"treasury_food={_trend_label(polity.treasury.get('food', 0.0))} treasury_wealth={_trend_label(polity.treasury.get('wealth', 0.0))} network_integrity={_trend_label(polity.command_network_state.get('integrity', 0.0))}",
    ]
