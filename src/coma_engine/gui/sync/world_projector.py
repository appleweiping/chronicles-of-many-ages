from __future__ import annotations

from coma_engine.core.state import WorldState
from coma_engine.gui.sync.entity_projector import project_entity_cards
from coma_engine.gui.sync.infoflow_projector import project_info_flows
from coma_engine.gui.sync.map_projector import project_tiles
from coma_engine.gui.sync.timeline_projector import project_timeline
from coma_engine.gui.types import TimeStateProjection, WorldFrameProjection


class WorldProjector:
    def project(self, world: WorldState, *, previous_frame: WorldFrameProjection | None = None) -> WorldFrameProjection:
        completed_phases = tuple(world.phase_snapshot_buffer.keys())
        current_phase_label = completed_phases[-1] if completed_phases else "Idle"
        tiles = project_tiles(world, previous_frame=previous_frame)
        dynamic_hotspots = tuple(
            tile.ref
            for tile in sorted(
                tiles,
                key=lambda item: (item.change_intensity + max(0.0, item.attention_delta), item.attention_score),
                reverse=True,
            )
            if tile.change_intensity >= 8.0 or tile.attention_delta >= 6.0 or tile.pressure_delta >= 5.0
        )[:8]
        return WorldFrameProjection(
            time_state=TimeStateProjection(
                step=world.current_step,
                phase_order=tuple(world.config.design_constants.phase_order),
                completed_phases=completed_phases,
                current_phase_label=current_phase_label,
            ),
            tiles=tiles,
            entity_cards=project_entity_cards(world),
            timeline_entries=project_timeline(world),
            info_flows=project_info_flows(world),
            dynamic_hotspots=dynamic_hotspots,
        )
