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
        f"food={settlement.stored_resources.get('food', 0.0):.1f} wood={settlement.stored_resources.get('wood', 0.0):.1f} ore={settlement.stored_resources.get('ore', 0.0):.1f}",
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
    ]
