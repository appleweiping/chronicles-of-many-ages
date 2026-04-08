from __future__ import annotations

from coma_engine.core.state import WorldState


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
