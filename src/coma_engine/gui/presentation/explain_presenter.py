from __future__ import annotations

from coma_engine.explain import debug_grade_step_report, player_grade_recent_history
from coma_engine.gui.types import WorldFrameProjection
from coma_engine.core.state import WorldState


def build_player_history(world: WorldState, frame: WorldFrameProjection, limit: int = 12) -> list[str]:
    del frame
    return player_grade_recent_history(world, limit=limit)


def build_debug_lines(world: WorldState, frame: WorldFrameProjection) -> list[str]:
    del frame
    return debug_grade_step_report(world, max(0, world.current_step - 1))
