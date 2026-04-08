from __future__ import annotations

import heapq

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


def shortest_path_cost(world: WorldState, start_tile_id: str, end_tile_id: str) -> float:
    if start_tile_id == end_tile_id:
        return 0.0
    frontier: list[tuple[float, str]] = [(0.0, start_tile_id)]
    seen: dict[str, float] = {start_tile_id: 0.0}
    while frontier:
        cost, tile_id = heapq.heappop(frontier)
        if tile_id == end_tile_id:
            return cost
        if cost > seen.get(tile_id, float("inf")):
            continue
        for neighbor_id in traversable_neighbors(world, tile_id):
            next_cost = cost + tile_path_cost(world, neighbor_id)
            if next_cost < seen.get(neighbor_id, float("inf")):
                seen[neighbor_id] = next_cost
                heapq.heappush(frontier, (next_cost, neighbor_id))
    return float("inf")
