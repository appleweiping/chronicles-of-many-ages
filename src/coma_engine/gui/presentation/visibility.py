from __future__ import annotations

from coma_engine.core.state import WorldState
from coma_engine.gui.types import VisibilityKind
from coma_engine.models.entities import Event


def visibility_for_ref(world: WorldState, ref: str | None) -> VisibilityKind:
    if ref is None:
        return "hidden"
    if ref.startswith("tile:"):
        return "confirmed" if ref in world.player_state.known_regions else "rumored"
    if ref in world.player_state.known_entities:
        return "confirmed"
    entity = world.entity_by_ref(ref)
    if entity is None:
        return "hidden"
    if ref.startswith(("settlement:", "polity:", "faction:", "war:")):
        return "rumored"
    return "hidden"


def visibility_for_event(world: WorldState, event: Event) -> VisibilityKind:
    if event.visibility_scope == "broad":
        return "confirmed"
    if event.location_tile_id and event.location_tile_id in world.player_state.known_regions:
        return "confirmed"
    if any(ref in world.player_state.known_entities for ref in event.participant_ids):
        return "inferred"
    return "rumored"
