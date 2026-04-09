"""Presentation adapters from GUI projections to player/debug views."""

from coma_engine.gui.presentation.entity_panels import build_inspection_panel
from coma_engine.gui.presentation.explain_presenter import build_debug_lines, build_timeline_groups
from coma_engine.gui.presentation.guidance_presenter import (
    build_alert_stack,
    build_chronicle_stream,
    build_top_bar,
    build_world_status,
    pick_default_focus_ref,
)
from coma_engine.gui.presentation.intervention_presenter import build_intervention_options
from coma_engine.gui.presentation.timeline_presenter import group_timeline_entries

__all__ = [
    "build_alert_stack",
    "build_chronicle_stream",
    "build_debug_lines",
    "build_inspection_panel",
    "build_intervention_options",
    "build_timeline_groups",
    "build_top_bar",
    "build_world_status",
    "group_timeline_entries",
    "pick_default_focus_ref",
]
