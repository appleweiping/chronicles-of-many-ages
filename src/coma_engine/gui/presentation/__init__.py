"""Presentation adapters from GUI projections to player/debug views."""

from coma_engine.gui.presentation.entity_panels import build_inspection_panel
from coma_engine.gui.presentation.explain_presenter import build_debug_lines, build_player_history
from coma_engine.gui.presentation.intervention_presenter import build_intervention_options
from coma_engine.gui.presentation.timeline_presenter import group_timeline_entries

__all__ = [
    "build_debug_lines",
    "build_inspection_panel",
    "build_intervention_options",
    "build_player_history",
    "group_timeline_entries",
]
