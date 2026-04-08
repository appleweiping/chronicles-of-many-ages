from __future__ import annotations

from coma_engine.core.state import WorldState


def tile_path_cost(world: WorldState, tile_id: str) -> float:
    tile = world.tiles[tile_id]
    return world.config.balance_parameters.path_costs[tile.terrain_type]


def traversable_neighbors(world: WorldState, tile_id: str) -> list[str]:
    return [
        neighbor_id
        for neighbor_id in world.tiles[tile_id].adjacent_tile_ids
        if tile_path_cost(world, neighbor_id) < 9999.0
    ]
