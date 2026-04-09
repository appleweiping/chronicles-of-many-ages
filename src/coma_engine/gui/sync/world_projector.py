from __future__ import annotations

from coma_engine.core.state import WorldState
from coma_engine.gui.sync.entity_projector import project_entity_cards
from coma_engine.gui.sync.infoflow_projector import project_info_flows
from coma_engine.gui.sync.map_projector import project_tiles
from coma_engine.gui.sync.timeline_projector import project_timeline
from coma_engine.gui.types import TimeStateProjection, WorldFrameProjection


class WorldProjector:
    def project(self, world: WorldState) -> WorldFrameProjection:
        completed_phases = tuple(world.phase_snapshot_buffer.keys())
        current_phase_label = completed_phases[-1] if completed_phases else "Idle"
        return WorldFrameProjection(
            time_state=TimeStateProjection(
                step=world.current_step,
                phase_order=tuple(world.config.design_constants.phase_order),
                completed_phases=completed_phases,
                current_phase_label=current_phase_label,
            ),
            tiles=project_tiles(world),
            entity_cards=project_entity_cards(world),
            timeline_entries=project_timeline(world),
            info_flows=project_info_flows(world),
        )
