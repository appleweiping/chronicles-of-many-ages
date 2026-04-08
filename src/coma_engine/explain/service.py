from __future__ import annotations

from coma_engine.core.state import WorldState


def debug_grade_action_explanations(world: WorldState, step: int) -> dict[str, dict[str, float]]:
    explanations = world.history_index["action_explanations"]  # type: ignore[index]
    return explanations.get(step, {})  # type: ignore[return-value]


def player_grade_recent_history(world: WorldState, limit: int = 5) -> list[str]:
    recent_events = sorted(world.events.values(), key=lambda event: (event.timestamp_step, event.id), reverse=True)
    return [
        f"第 {event.timestamp_step} 步：{event.event_type} ({event.outcome_summary_code})"
        for event in recent_events[:limit]
    ]
