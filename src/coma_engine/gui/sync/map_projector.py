from __future__ import annotations

from coma_engine.core.state import WorldState
from coma_engine.gui.types import TileRenderProjection


def project_tiles(world: WorldState) -> tuple[TileRenderProjection, ...]:
    projections: list[TileRenderProjection] = []
    for tile in sorted(world.tiles.values(), key=lambda item: (item.y, item.x)):
        projections.append(
            TileRenderProjection(
                ref=tile.id,
                x=tile.x,
                y=tile.y,
                terrain_type=tile.terrain_type,
                settlement_id=tile.settlement_id,
                controller_faction_id=tile.controller_faction_id,
                controller_polity_id=tile.controller_polity_id,
                effective_yield_total=round(sum(tile.effective_yield.values()) if tile.effective_yield else sum(tile.base_yield.values()), 2),
                control_pressure=round(tile.effective_control_pressure, 2),
                local_unrest=round(tile.local_unrest, 2),
                visibility_strength=round(tile.effective_visibility, 2),
                resident_count=len(tile.resident_npc_ids),
                resource_stock_total=round(sum(tile.current_stock.values()), 2),
                activity_level=round(len(tile.resident_npc_ids) * 6.0 + tile.local_unrest + tile.effective_control_pressure * 0.1, 2),
            )
        )
    return tuple(projections)
