from __future__ import annotations

from coma_engine.core.state import WorldState
from coma_engine.explain import debug_grade_step_report
from coma_engine.gui.types import TimelineGroupProjection, TimelineRowProjection, WorldFrameProjection


def _humanize(code: str) -> str:
    return code.replace("_", " ").title()


def build_timeline_groups(world: WorldState, frame: WorldFrameProjection, *, historical_scale: bool = False, limit: int = 18) -> tuple[TimelineGroupProjection, ...]:
    del world
    major: list[TimelineRowProjection] = []
    regional: list[TimelineRowProjection] = []
    rumors: list[TimelineRowProjection] = []

    entries = frame.timeline_entries if historical_scale else frame.timeline_entries[:limit]
    for entry in entries:
        target_ref = entry.location_ref or (entry.participant_refs[0] if entry.participant_refs else None)
        row = TimelineRowProjection(
            headline=_humanize(entry.event_type),
            detail=f"Step {entry.step} · {_humanize(entry.outcome_summary_code)} · {_humanize(entry.layer)}",
            target_ref=target_ref,
            tone="major" if entry.importance >= 70.0 else "notable",
        )
        if entry.visibility in {"rumored", "inferred"}:
            rumors.append(TimelineRowProjection(row.headline, f"{row.detail} · {entry.visibility}", row.target_ref, "rumor"))
        elif entry.importance >= 70.0 or entry.layer == "civilization_node":
            major.append(row)
        else:
            regional.append(row)

    groups: list[TimelineGroupProjection] = []
    if major:
        groups.append(TimelineGroupProjection("Civilization Nodes" if historical_scale else "Major Shifts", tuple(major[:8])))
    if regional:
        groups.append(TimelineGroupProjection("Regional Chronicle", tuple(regional[:10])))
    if rumors:
        groups.append(TimelineGroupProjection("Signals And Rumors", tuple(rumors[:6])))
    return tuple(groups)


def build_debug_lines(world: WorldState, frame: WorldFrameProjection) -> list[str]:
    del frame
    return debug_grade_step_report(world, max(0, world.current_step - 1))
