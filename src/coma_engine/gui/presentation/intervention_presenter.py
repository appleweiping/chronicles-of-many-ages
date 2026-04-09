from __future__ import annotations

from coma_engine.core.state import WorldState
from coma_engine.gui.types import InterventionOptionProjection


def _resource_option(target_ref: str) -> InterventionOptionProjection:
    return InterventionOptionProjection(
        action_id="resource",
        label="Bless Harvest",
        description="Push relief and abundance toward this place through the existing resource-modifier path.",
        target_ref=target_ref,
        channel="modifier",
        enabled=True,
        impact_hint="Best for instability, shortages, and visible settlement pressure.",
        emphasis="stabilize",
        preview_lines=(
            "Likely to ease local strain over the next few steps.",
            "Acts through the formal modifier channel.",
            "Most useful where food pressure or unrest is already visible.",
        ),
    )


def _rumor_option(target_ref: str) -> InterventionOptionProjection:
    return InterventionOptionProjection(
        action_id="rumor",
        label="Seed Rumor",
        description="Inject a new formal information packet into this region and let propagation carry it.",
        target_ref=target_ref,
        channel="info_packet",
        enabled=target_ref.startswith("tile:"),
        impact_hint="Useful when you want attention, uncertainty, or belief pressure to spread.",
        emphasis="info",
        preview_lines=(
            "Likely to increase rumor pressure in this region.",
            "Depends on visibility, local spread, and existing information flow.",
            "Will not predict exact downstream interpretation.",
        ),
    )


def _miracle_option(target_ref: str) -> InterventionOptionProjection:
    return InterventionOptionProjection(
        action_id="miracle",
        label="Spread Omen",
        description="Create a dramatic formal event in the selected region without bypassing the event system.",
        target_ref=target_ref,
        channel="event",
        enabled=target_ref.startswith("tile:"),
        impact_hint="High-visibility move for moments that should feel decisive or unforgettable.",
        emphasis="mystic",
        preview_lines=(
            "Will enter through the event channel rather than direct state editing.",
            "Likely to create strong visible interpretation if the region can see it.",
            "Exact follow-on effects remain formal-system dependent.",
        ),
    )


def _bless_option(target_ref: str) -> InterventionOptionProjection:
    return InterventionOptionProjection(
        action_id="bless",
        label="Favor Leader",
        description="Channel a formal blessing toward this figure through the approved modifier path.",
        target_ref=target_ref,
        channel="modifier",
        enabled=True,
        impact_hint="Useful when a visible actor seems fragile, embattled, or politically important.",
        emphasis="support",
        preview_lines=(
            "Targets the selected figure only.",
            "Resolves through the formal modifier channel next step.",
            "Exact downstream outcome remains uncertain.",
        ),
    )


def _anchor_tile_for(world: WorldState, target_ref: str) -> str | None:
    entity = world.entity_by_ref(target_ref)
    if entity is None:
        return None
    tile_ref = getattr(entity, "location_tile_id", None) or getattr(entity, "core_tile_id", None)
    if tile_ref is not None:
        return tile_ref
    settlement_ref = getattr(entity, "capital_settlement_id", None) or getattr(entity, "settlement_id", None)
    settlement = world.entity_by_ref(settlement_ref) if settlement_ref else None
    if settlement is not None:
        return getattr(settlement, "core_tile_id", None)
    participant_polities = getattr(entity, "participant_polity_ids", None)
    if participant_polities:
        for polity_id in participant_polities:
            polity = world.entity_by_ref(polity_id)
            settlement = world.entity_by_ref(getattr(polity, "capital_settlement_id", None)) if polity else None
            tile_ref = getattr(settlement, "core_tile_id", None)
            if tile_ref is not None:
                return tile_ref
    return None


def _anchor_npc_for(world: WorldState, target_ref: str) -> str | None:
    entity = world.entity_by_ref(target_ref)
    if entity is None:
        return None
    npc_ref = getattr(entity, "leader_npc_id", None) or getattr(entity, "ruler_npc_id", None)
    if npc_ref is not None:
        return npc_ref
    participant_polities = getattr(entity, "participant_polity_ids", None)
    if participant_polities:
        polity = world.entity_by_ref(participant_polities[0])
        return getattr(polity, "ruler_npc_id", None) if polity else None
    return None


def build_intervention_options(world: WorldState, target_ref: str) -> tuple[InterventionOptionProjection, ...]:
    if target_ref.startswith("npc:"):
        return (_bless_option(target_ref),)
    if target_ref.startswith(("tile:", "settlement:")):
        return (_resource_option(target_ref), _rumor_option(target_ref), _miracle_option(target_ref))

    derived: list[InterventionOptionProjection] = []
    anchor_npc = _anchor_npc_for(world, target_ref)
    anchor_tile = _anchor_tile_for(world, target_ref)
    if anchor_npc is not None:
        derived.append(_bless_option(anchor_npc))
    if anchor_tile is not None:
        derived.append(_resource_option(anchor_tile))
        derived.append(_rumor_option(anchor_tile))
        derived.append(_miracle_option(anchor_tile))
    deduped: dict[tuple[str, str], InterventionOptionProjection] = {}
    for option in derived:
        deduped[(option.action_id, option.target_ref)] = option
    return tuple(deduped.values())
