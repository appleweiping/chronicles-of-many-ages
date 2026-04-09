from __future__ import annotations

from coma_engine.core.state import WorldState
from coma_engine.gui.presentation.visibility import visibility_for_ref
from coma_engine.gui.types import TileRenderProjection, WorldFrameProjection


def _attention_band(score: float) -> str:
    if score >= 70.0:
        return "critical"
    if score >= 45.0:
        return "urgent"
    if score >= 22.0:
        return "watch"
    return "calm"


def project_tiles(world: WorldState, *, previous_frame: WorldFrameProjection | None = None) -> tuple[TileRenderProjection, ...]:
    previous_tiles = {tile.ref: tile for tile in previous_frame.tiles} if previous_frame is not None else {}
    recent_event_pressure: dict[str, float] = {}
    recent_signal_pressure: dict[str, float] = {}
    recent_threshold = max(0, world.current_step - 2)
    for event in world.events.values():
        if event.location_tile_id is None or event.timestamp_step < recent_threshold:
            continue
        recent_event_pressure[event.location_tile_id] = recent_event_pressure.get(event.location_tile_id, 0.0) + (
            max(8.0, event.importance * 0.22)
        )
    for packet in world.info_packets:
        if packet.location_ref is None or not packet.location_ref.startswith("tile:"):
            continue
        recent_signal_pressure[packet.location_ref] = recent_signal_pressure.get(packet.location_ref, 0.0) + (
            packet.strength * 0.35
        )

    projections: list[TileRenderProjection] = []
    for tile in sorted(world.tiles.values(), key=lambda item: (item.y, item.x)):
        event_pressure = recent_event_pressure.get(tile.id, 0.0)
        signal_level = round(recent_signal_pressure.get(tile.id, 0.0), 2)
        effective_yield_total = round(sum(tile.effective_yield.values()) if tile.effective_yield else sum(tile.base_yield.values()), 2)
        resource_stock_total = round(sum(tile.current_stock.values()), 2)
        power_level = round(
            (28.0 if tile.settlement_id else 0.0)
            + (22.0 if tile.controller_polity_id else 0.0)
            + min(25.0, tile.effective_control_pressure * 0.12),
            2,
        )
        scarcity_level = round(max(0.0, 42.0 - effective_yield_total * 2.4 + max(0.0, 14.0 - resource_stock_total)), 2)
        command_stress_level = round(min(100.0, tile.local_unrest * 0.7 + max(0.0, tile.effective_control_pressure - 40.0) * 0.35), 2)
        activity_level = round(len(tile.resident_npc_ids) * 6.0 + tile.local_unrest + tile.effective_control_pressure * 0.1, 2)
        attention_score = round(
            min(
                100.0,
                event_pressure
                + tile.local_unrest * 0.85
                + tile.effective_control_pressure * 0.05
                + len(tile.resident_npc_ids) * 5.5
                + (10.0 if tile.settlement_id else 0.0)
                + signal_level * 0.45,
            ),
            2,
        )
        previous = previous_tiles.get(tile.id)
        activity_delta = round(activity_level - previous.activity_level, 2) if previous is not None else 0.0
        attention_delta = round(attention_score - previous.attention_score, 2) if previous is not None else 0.0
        pressure_delta = round(command_stress_level - previous.command_stress_level, 2) if previous is not None else 0.0
        signal_delta = round(signal_level - previous.signal_level, 2) if previous is not None else 0.0
        change_intensity = round(
            abs(activity_delta) * 0.32 + abs(attention_delta) * 0.4 + abs(pressure_delta) * 0.42 + abs(signal_delta) * 0.25,
            2,
        )
        if attention_delta >= 4.0 or pressure_delta >= 4.0 or signal_delta >= 3.0:
            change_direction = "rising"
        elif attention_delta <= -4.0 or pressure_delta <= -4.0:
            change_direction = "falling"
        else:
            change_direction = "steady"
        attention_tags: list[str] = []
        if event_pressure >= 20.0:
            attention_tags.append("major change")
        if tile.local_unrest >= 40.0:
            attention_tags.append("instability")
        if power_level >= 38.0:
            attention_tags.append("power center")
        if signal_level >= 12.0:
            attention_tags.append("rumor traffic")
        if tile.resident_npc_ids and tile.effective_control_pressure >= 70.0:
            attention_tags.append("heavy control")
        if pressure_delta >= 5.0:
            attention_tags.append("deteriorating")
        elif pressure_delta <= -5.0:
            attention_tags.append("recovering")
        if signal_delta >= 4.0:
            attention_tags.append("spreading signal")
        if not attention_tags:
            attention_tags.append("quiet region")
        projections.append(
            TileRenderProjection(
                ref=tile.id,
                x=tile.x,
                y=tile.y,
                terrain_type=tile.terrain_type,
                settlement_id=tile.settlement_id,
                controller_faction_id=tile.controller_faction_id,
                controller_polity_id=tile.controller_polity_id,
                effective_yield_total=effective_yield_total,
                control_pressure=round(tile.effective_control_pressure, 2),
                local_unrest=round(tile.local_unrest, 2),
                visibility_strength=round(tile.effective_visibility, 2),
                resident_count=len(tile.resident_npc_ids),
                resource_stock_total=resource_stock_total,
                activity_level=activity_level,
                attention_score=attention_score,
                attention_band=_attention_band(attention_score),
                attention_tags=tuple(attention_tags),
                known_visibility=visibility_for_ref(world, tile.id),
                power_level=power_level,
                signal_level=signal_level,
                scarcity_level=scarcity_level,
                command_stress_level=command_stress_level,
                activity_delta=activity_delta,
                attention_delta=attention_delta,
                pressure_delta=pressure_delta,
                signal_delta=signal_delta,
                change_intensity=change_intensity,
                change_direction=change_direction,
            )
        )
    return tuple(projections)
