from __future__ import annotations

from coma_engine.core.state import WorldState
from coma_engine.gui.presentation.visibility import visibility_for_ref
from coma_engine.gui.types import EntityCardProjection


def project_entity_cards(world: WorldState) -> tuple[EntityCardProjection, ...]:
    cards: list[EntityCardProjection] = []
    for tile in sorted(world.tiles.values(), key=lambda item: item.id):
        cards.append(
            EntityCardProjection(
                ref=tile.id,
                label=f"{tile.id} {tile.terrain_type}",
                entity_kind="tile",
                location_ref=tile.id,
                related_refs=tuple(ref for ref in (tile.settlement_id, tile.controller_faction_id, tile.controller_polity_id) if ref),
                visibility=visibility_for_ref(world, tile.id),
            )
        )
    for npc in sorted(world.npcs.values(), key=lambda item: item.id):
        cards.append(
            EntityCardProjection(
                ref=npc.id,
                label=f"{npc.id} {npc.name}",
                entity_kind="npc",
                location_ref=npc.location_tile_id,
                related_refs=tuple(ref for ref in (npc.settlement_id, npc.faction_id, npc.polity_id) if ref),
                visibility=visibility_for_ref(world, npc.id),
            )
        )
    for settlement in sorted((world.settlements | world.archived_settlements).values(), key=lambda item: item.id):
        cards.append(
            EntityCardProjection(
                ref=settlement.id,
                label=f"{settlement.id} {settlement.name}",
                entity_kind="settlement",
                location_ref=settlement.core_tile_id,
                related_refs=tuple(ref for ref in (settlement.faction_id, settlement.polity_id) if ref),
                visibility=visibility_for_ref(world, settlement.id),
            )
        )
    for faction in sorted((world.factions | world.archived_factions).values(), key=lambda item: item.id):
        cards.append(
            EntityCardProjection(
                ref=faction.id,
                label=f"{faction.id} {faction.name}",
                entity_kind="faction",
                location_ref=None,
                related_refs=tuple([faction.leader_npc_id, *faction.settlement_ids[:2]]),
                visibility=visibility_for_ref(world, faction.id),
            )
        )
    for polity in sorted((world.polities | world.archived_polities).values(), key=lambda item: item.id):
        cards.append(
            EntityCardProjection(
                ref=polity.id,
                label=f"{polity.id} {polity.name}",
                entity_kind="polity",
                location_ref=polity.capital_settlement_id,
                related_refs=tuple([polity.ruler_npc_id, polity.capital_settlement_id, *polity.member_settlement_ids[:2]]),
                visibility=visibility_for_ref(world, polity.id),
            )
        )
    for war in sorted(world.war_states.values(), key=lambda item: item.id):
        cards.append(
            EntityCardProjection(
                ref=war.id,
                label=war.id,
                entity_kind="war",
                location_ref=None,
                related_refs=tuple(war.participant_polity_ids),
                visibility="inferred" if any(ref in world.player_state.known_entities for ref in war.participant_polity_ids) else "rumored",
            )
        )
    return tuple(cards)
