from __future__ import annotations

from coma_engine.core.state import WorldState


def _remove_once(items: list[str], target: str) -> None:
    if target in items:
        items.remove(target)


def move_npc_to_tile(world: WorldState, npc_id: str, tile_id: str) -> None:
    npc = world.npcs[npc_id]
    old_tile = world.tiles[npc.location_tile_id]
    new_tile = world.tiles[tile_id]
    _remove_once(old_tile.resident_npc_ids, npc_id)
    npc.location_tile_id = tile_id
    if npc_id not in new_tile.resident_npc_ids:
        new_tile.resident_npc_ids.append(npc_id)


def assign_npc_settlement(world: WorldState, npc_id: str, settlement_id: str | None) -> None:
    npc = world.npcs[npc_id]
    if npc.settlement_id and npc.settlement_id in world.settlements:
        _remove_once(world.settlements[npc.settlement_id].resident_npc_ids, npc_id)
    npc.settlement_id = settlement_id
    if settlement_id and settlement_id in world.settlements:
        settlement = world.settlements[settlement_id]
        if npc_id not in settlement.resident_npc_ids:
            settlement.resident_npc_ids.append(npc_id)


def assign_npc_faction(world: WorldState, npc_id: str, faction_id: str | None) -> None:
    npc = world.npcs[npc_id]
    if npc.faction_id and npc.faction_id in world.factions:
        _remove_once(world.factions[npc.faction_id].member_npc_ids, npc_id)
    npc.faction_id = faction_id
    if faction_id and faction_id in world.factions:
        faction = world.factions[faction_id]
        if npc_id not in faction.member_npc_ids:
            faction.member_npc_ids.append(npc_id)


def assign_npc_polity(world: WorldState, npc_id: str, polity_id: str | None) -> None:
    world.npcs[npc_id].polity_id = polity_id


def assign_settlement_tiles(world: WorldState, settlement_id: str, tile_ids: list[str]) -> None:
    settlement = world.settlements[settlement_id]
    for tile in world.tiles.values():
        if tile.settlement_id == settlement_id and tile.id not in tile_ids:
            tile.settlement_id = None
    settlement.member_tile_ids = list(dict.fromkeys(tile_ids))
    for tile_id in settlement.member_tile_ids:
        world.tiles[tile_id].settlement_id = settlement_id


def assign_settlement_faction(world: WorldState, settlement_id: str, faction_id: str | None) -> None:
    settlement = world.settlements[settlement_id]
    if settlement.faction_id and settlement.faction_id in world.factions:
        _remove_once(world.factions[settlement.faction_id].settlement_ids, settlement_id)
    settlement.faction_id = faction_id
    if faction_id and faction_id in world.factions:
        faction = world.factions[faction_id]
        if settlement_id not in faction.settlement_ids:
            faction.settlement_ids.append(settlement_id)


def assign_settlement_polity(world: WorldState, settlement_id: str, polity_id: str | None) -> None:
    settlement = world.settlements[settlement_id]
    if settlement.polity_id and settlement.polity_id in world.polities:
        _remove_once(world.polities[settlement.polity_id].member_settlement_ids, settlement_id)
    settlement.polity_id = polity_id
    if polity_id and polity_id in world.polities:
        polity = world.polities[polity_id]
        if settlement_id not in polity.member_settlement_ids:
            polity.member_settlement_ids.append(settlement_id)


def reconcile_references(world: WorldState) -> None:
    for tile in world.tiles.values():
        tile.resident_npc_ids = []
    for settlement in world.settlements.values():
        settlement.resident_npc_ids = []
    for faction in world.factions.values():
        faction.member_npc_ids = []
        faction.settlement_ids = list(dict.fromkeys(faction.settlement_ids))
    for polity in world.polities.values():
        polity.member_settlement_ids = list(dict.fromkeys(polity.member_settlement_ids))
        polity.member_faction_ids = list(dict.fromkeys(polity.member_faction_ids))

    for npc in world.npcs.values():
        tile = world.tiles.get(npc.location_tile_id)
        if tile and npc.id not in tile.resident_npc_ids:
            tile.resident_npc_ids.append(npc.id)
        if npc.settlement_id in world.settlements:
            settlement = world.settlements[npc.settlement_id]
            if npc.id not in settlement.resident_npc_ids:
                settlement.resident_npc_ids.append(npc.id)
        if npc.faction_id in world.factions:
            faction = world.factions[npc.faction_id]
            if npc.id not in faction.member_npc_ids:
                faction.member_npc_ids.append(npc.id)

    for settlement in world.settlements.values():
        for tile_id in settlement.member_tile_ids:
            if tile_id in world.tiles:
                world.tiles[tile_id].settlement_id = settlement.id
        if settlement.faction_id in world.factions:
            faction = world.factions[settlement.faction_id]
            if settlement.id not in faction.settlement_ids:
                faction.settlement_ids.append(settlement.id)
        if settlement.polity_id in world.polities:
            polity = world.polities[settlement.polity_id]
            if settlement.id not in polity.member_settlement_ids:
                polity.member_settlement_ids.append(settlement.id)


def validate_reference_consistency(world: WorldState) -> list[str]:
    errors: list[str] = []
    for npc in world.npcs.values():
        tile = world.tiles.get(npc.location_tile_id)
        if tile and npc.id not in tile.resident_npc_ids:
            errors.append(f"{npc.id} missing from tile mirror")
        if npc.settlement_id:
            settlement = world.settlements.get(npc.settlement_id)
            if settlement and npc.id not in settlement.resident_npc_ids:
                errors.append(f"{npc.id} missing from settlement mirror")
        if npc.faction_id:
            faction = world.factions.get(npc.faction_id)
            if faction and npc.id not in faction.member_npc_ids:
                errors.append(f"{npc.id} missing from faction mirror")
    for settlement in world.settlements.values():
        for tile_id in settlement.member_tile_ids:
            tile = world.tiles.get(tile_id)
            if tile and tile.settlement_id != settlement.id:
                errors.append(f"{settlement.id} tile mirror mismatch on {tile_id}")
        if settlement.faction_id:
            faction = world.factions.get(settlement.faction_id)
            if faction and settlement.id not in faction.settlement_ids:
                errors.append(f"{settlement.id} missing from faction settlement mirror")
        if settlement.polity_id:
            polity = world.polities.get(settlement.polity_id)
            if polity and settlement.id not in polity.member_settlement_ids:
                errors.append(f"{settlement.id} missing from polity settlement mirror")
    return errors
