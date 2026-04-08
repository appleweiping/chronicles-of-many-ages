from __future__ import annotations

from coma_engine.config.schema import ConfigSchema
from coma_engine.core.state import WorldState
from coma_engine.core.transfers import (
    assign_npc_faction,
    assign_npc_settlement,
    assign_settlement_faction,
    assign_settlement_tiles,
)
from coma_engine.models.entities import Faction, Goal, NPC, RelationEntry, Settlement, Tile
from coma_engine.models.perception import PerceivedState


def create_world(config: ConfigSchema) -> WorldState:
    world = WorldState(config=config)
    world.rng.seed(config.seed)
    _generate_tiles(world)
    _generate_npcs(world)
    _seed_early_organizations(world)
    return world


def _generate_tiles(world: WorldState) -> None:
    width = world.config.balance_parameters.world_width
    height = world.config.balance_parameters.world_height
    terrains = tuple(world.config.balance_parameters.path_costs.keys())
    for y in range(height):
        for x in range(width):
            tile_id = world.next_id("tile")
            terrain = terrains[(x + y + world.config.seed) % len(terrains)]
            if x in {2, 5} and y in {2, 5}:
                terrain = "plains"
            base_yield = dict(world.config.balance_parameters.terrain_yields[terrain])
            world.tiles[tile_id] = Tile(
                id=tile_id,
                x=x,
                y=y,
                terrain_type=terrain,
                base_yield=base_yield,
                current_stock={key: value * 2.0 for key, value in base_yield.items()},
                fertility=70.0 if terrain == "plains" else 45.0,
                danger=20.0 if terrain == "plains" else 35.0,
                capacity=6.0 if terrain == "plains" else 4.0,
            )
    coords = {(tile.x, tile.y): tile.id for tile in world.tiles.values()}
    for tile in world.tiles.values():
        tile.adjacent_tile_ids = [
            coords[(tile.x + dx, tile.y + dy)]
            for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0))
            if (tile.x + dx, tile.y + dy) in coords
        ]
        tile.effective_path_cost = world.config.balance_parameters.path_costs[tile.terrain_type]


def _generate_npcs(world: WorldState) -> None:
    plains = [tile for tile in world.tiles.values() if tile.terrain_type == "plains"]
    spawn_tiles = plains[: max(1, min(len(plains), 6))]
    for index in range(world.config.balance_parameters.initial_population):
        tile = spawn_tiles[index % len(spawn_tiles)]
        npc_id = world.next_id("npc")
        world.npcs[npc_id] = NPC(
            id=npc_id,
            name=f"NPC {index + 1}",
            alive=True,
            age=18.0 + (index % 25),
            culture_id=f"culture:{index % world.config.balance_parameters.initial_culture_count}",
            family_id=f"family:{index % world.config.balance_parameters.initial_family_count}",
            location_tile_id=tile.id,
            health=82.0,
            settlement_id=None,
            faction_id=None,
            polity_id=None,
            role="commoner" if index > 2 else "elite",
            office_rank=4 if index == 0 else (3 if index == 1 else 1),
            personal_inventory={"food": 4.0, "wood": 0.0, "ore": 0.0, "wealth": 0.0},
            needs={"food": 35.0, "safety": 40.0, "social": 30.0, "status": 25.0, "meaning": 20.0},
            personality={"risk_tolerance": 45.0, "familiality": 55.0, "ambition": 60.0 if index == 0 else 35.0},
            abilities={"foraging": 55.0, "politics": 70.0 if index == 0 else 30.0, "warfare": 40.0},
            beliefs={"miracle_credibility": 25.0, "destiny": 50.0, "legitimacy_form": 45.0},
            relationships={},
            memory_ids=[],
            long_term_goal=Goal(goal_type="FOUND_POLITY" if index == 0 else "SURVIVE"),
            active_modifier_ids=[],
            cooldowns={},
            current_action_ref=None,
            perceived_state=PerceivedState(),
        )
        tile.resident_npc_ids.append(npc_id)

    npc_ids = list(world.npcs.keys())
    for npc_id in npc_ids:
        npc = world.npcs[npc_id]
        for other_id in npc_ids:
            if other_id == npc_id:
                continue
            other = world.npcs[other_id]
            if other.family_id == npc.family_id or other.location_tile_id == npc.location_tile_id:
                npc.relationships[other_id] = RelationEntry(affinity=10.0, trust=8.0, familiarity=25.0)


def _seed_early_organizations(world: WorldState) -> None:
    grouped: dict[str, list[str]] = {}
    for npc in world.npcs.values():
        grouped.setdefault(npc.location_tile_id, []).append(npc.id)
    if not grouped:
        return

    largest_tile_id = max(grouped, key=lambda tile_id: len(grouped[tile_id]))
    residents = grouped[largest_tile_id]
    settlement_id = world.next_id("settlement")
    world.settlements[settlement_id] = Settlement(
        id=settlement_id,
        name="Founders Camp",
        core_tile_id=largest_tile_id,
        member_tile_ids=[largest_tile_id],
        resident_npc_ids=[],
        stored_resources={"food": 18.0, "wood": 6.0, "ore": 2.0, "wealth": 1.0},
        security_level=52.0,
        stability=58.0,
        faction_id=None,
        polity_id=None,
        active_modifier_ids=[],
        labor_pool=float(len(residents)),
    )
    assign_settlement_tiles(world, settlement_id, [largest_tile_id])
    for npc_id in residents:
        assign_npc_settlement(world, npc_id, settlement_id)

    faction_id = world.next_id("faction")
    world.factions[faction_id] = Faction(
        id=faction_id,
        name="Founder Circle",
        leader_npc_id=residents[0],
        member_npc_ids=[],
        settlement_ids=[],
        support_score=62.0,
        cohesion=60.0,
        agenda_type="order",
        legitimacy_seed_components={"kinship": 45.0, "provision": 55.0},
        active_modifier_ids=[],
    )
    for npc_id in residents[:3]:
        assign_npc_faction(world, npc_id, faction_id)
    assign_settlement_faction(world, settlement_id, faction_id)
