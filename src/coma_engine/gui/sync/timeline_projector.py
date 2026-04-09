from __future__ import annotations

from coma_engine.core.state import WorldState
from coma_engine.gui.presentation.visibility import visibility_for_event
from coma_engine.gui.types import TimelineEntryProjection


def project_timeline(world: WorldState, limit: int = 120) -> tuple[TimelineEntryProjection, ...]:
    layer_lookup: dict[str, str] = {}
    event_layers: dict[str, list[str]] = world.history_index["event_layers"]  # type: ignore[assignment]
    for layer, event_ids in event_layers.items():
        for event_id in event_ids:
            layer_lookup[event_id] = layer

    entries = sorted(world.events.values(), key=lambda event: (event.timestamp_step, event.importance, event.id), reverse=True)
    projections: list[TimelineEntryProjection] = []
    for event in entries[:limit]:
        projections.append(
            TimelineEntryProjection(
                event_id=event.id,
                event_type=event.event_type,
                step=event.timestamp_step,
                layer=layer_lookup.get(event.id, "raw_event"),
                importance=event.importance,
                location_ref=event.location_tile_id,
                participant_refs=tuple(event.participant_ids),
                cause_refs=tuple(event.cause_refs),
                outcome_summary_code=event.outcome_summary_code,
                visibility=visibility_for_event(world, event),
            )
        )
    return tuple(projections)
