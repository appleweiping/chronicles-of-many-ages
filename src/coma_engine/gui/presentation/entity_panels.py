from __future__ import annotations

from coma_engine.core.state import WorldState
from coma_engine.explain import (
    debug_grade_step_report,
    player_grade_npc_summary,
    player_grade_polity_recent_factors,
    player_grade_polity_summary,
    player_grade_settlement_recent_factors,
    player_grade_settlement_summary,
    player_grade_war_recent_factors,
    player_grade_war_summary,
)
from coma_engine.gui.presentation.schemas import SCHEMA_REGISTRY
from coma_engine.gui.types import (
    InspectionFieldProjection,
    InspectionPanelProjection,
    InspectionSectionProjection,
)


def _lines_to_section(title: str, lines: list[str], visibility: str = "confirmed") -> InspectionSectionProjection:
    return InspectionSectionProjection(
        title=title,
        fields=tuple(
            InspectionFieldProjection(key=f"{title}:{index}", label=f"{index + 1}", value=line, visibility=visibility)
            for index, line in enumerate(lines)
        ),
    )


def build_inspection_panel(world: WorldState, ref: str, *, debug_mode: bool = False) -> InspectionPanelProjection:
    prefix = ref.split(":", 1)[0]
    schema = SCHEMA_REGISTRY.get(prefix, SCHEMA_REGISTRY["tile"])
    sections: list[InspectionSectionProjection] = []

    if prefix == "npc":
        sections.append(_lines_to_section("overview", player_grade_npc_summary(world, ref)))
    elif prefix == "settlement":
        sections.append(_lines_to_section("overview", player_grade_settlement_summary(world, ref)))
        sections.append(_lines_to_section("causes", player_grade_settlement_recent_factors(world, ref)))
    elif prefix == "polity":
        sections.append(_lines_to_section("overview", player_grade_polity_summary(world, ref)))
        sections.append(_lines_to_section("causes", player_grade_polity_recent_factors(world, ref)))
    elif prefix == "war":
        sections.append(_lines_to_section("overview", player_grade_war_summary(world, ref)))
        sections.append(_lines_to_section("causes", player_grade_war_recent_factors(world, ref)))
    else:
        entity = world.entity_by_ref(ref)
        sections.append(_lines_to_section("overview", [f"{ref}", repr(entity) if debug_mode else "No player-grade panel yet"]))

    if debug_mode:
        debug_lines = [line for line in debug_grade_step_report(world, max(0, world.current_step - 1)) if ref in line][:12]
        if debug_lines:
            sections.append(_lines_to_section("debug", debug_lines, visibility="confirmed"))

    return InspectionPanelProjection(
        ref=ref,
        title=f"{schema.title} {ref}",
        entity_kind=schema.entity_kind,
        sections=tuple(sections),
        debug_mode=debug_mode,
    )
