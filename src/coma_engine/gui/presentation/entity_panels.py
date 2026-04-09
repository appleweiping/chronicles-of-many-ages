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
from coma_engine.gui.presentation.labels import power_label, resource_condition_label, security_label, stability_label
from coma_engine.gui.presentation.schemas import SCHEMA_REGISTRY
from coma_engine.gui.presentation.visibility import visibility_for_ref
from coma_engine.gui.types import InspectionFieldProjection, InspectionPanelProjection, InspectionSectionProjection


def _lines_to_section(title: str, lines: list[str], visibility: str = "confirmed") -> InspectionSectionProjection:
    return InspectionSectionProjection(
        title=title,
        fields=tuple(
            InspectionFieldProjection(key=f"{title}:{index}", label=f"{index + 1}", value=line, visibility=visibility)
            for index, line in enumerate(lines)
        ),
    )


def _knowledge_lines(world: WorldState, ref: str) -> list[str]:
    visibility = visibility_for_ref(world, ref)
    if visibility == "confirmed":
        return ["Confirmed by direct player knowledge.", "Details shown here are interpreted summaries, not raw internals."]
    if visibility == "inferred":
        return ["Inferred from visible events and affiliations.", "Some details remain uncertain."]
    if visibility == "rumored":
        return ["Known mostly through rumor or distant reports.", "Treat details as partial and unstable."]
    return ["Currently outside player knowledge."]


def _tile_overview(world: WorldState, ref: str) -> tuple[list[str], str, tuple[str, ...]]:
    tile = world.tiles.get(ref)
    if tile is None:
        return [f"{ref} not found"], "No readable local context exists here.", ("unknown",)
    recent_events = [
        event for event in world.events.values() if event.location_tile_id == ref and event.timestamp_step >= max(0, world.current_step - 2)
    ]
    packet_count = sum(1 for packet in world.info_packets if packet.location_ref == ref)
    summary = "Quiet ground with no obvious immediate pressure."
    if tile.local_unrest >= 45.0:
        summary = "Visible local tension is shaping this region right now."
    elif recent_events:
        summary = "Recent events have made this region worth attention."
    elif tile.controller_polity_id or tile.settlement_id:
        summary = "This region sits under visible organized attention."
    tags = (
        tile.terrain_type,
        "settled" if tile.settlement_id else "wild",
        "restless" if tile.local_unrest >= 35.0 else "calm",
    )
    return (
        [
            f"Terrain: {tile.terrain_type}",
            f"Controller: {tile.controller_polity_id or 'none visible'}",
            f"Settlement: {tile.settlement_id or 'none visible'}",
            f"Visible activity: {len(tile.resident_npc_ids)} residents · {len(recent_events)} recent events · {packet_count} rumor traces",
            f"Resource trend: yield {sum(tile.effective_yield.values()) if tile.effective_yield else sum(tile.base_yield.values()):.1f}",
        ],
        summary,
        tags,
    )


def build_inspection_panel(world: WorldState, ref: str, *, debug_mode: bool = False) -> InspectionPanelProjection:
    prefix = ref.split(":", 1)[0]
    schema = SCHEMA_REGISTRY.get(prefix, SCHEMA_REGISTRY["tile"])
    sections: list[InspectionSectionProjection] = []
    summary = "No summary available."
    status_tags: tuple[str, ...] = ()
    affordances: list[str] = ["Focus on map", "Show related entities"]

    if prefix == "npc":
        lines = player_grade_npc_summary(world, ref)
        npc = world.npcs.get(ref)
        summary = "A visible figure whose immediate condition and affiliations may shape nearby events."
        if npc is not None:
            status_tags = (
                npc.role,
                "frail" if npc.health < 45.0 else "steady",
                "prominent" if npc.office_rank >= 45.0 else "local",
            )
            if npc.settlement_id:
                affordances.append("Inspect associated settlement")
            if npc.polity_id:
                affordances.append("Inspect associated polity")
        sections.append(_lines_to_section("identity", lines))
    elif prefix == "settlement":
        settlement = world.entity_by_ref(ref)
        lines = player_grade_settlement_summary(world, ref)
        causes = player_grade_settlement_recent_factors(world, ref)
        if settlement is not None:
            summary = (
                f"{getattr(settlement, 'name', ref)} currently reads as {stability_label(getattr(settlement, 'stability', 0.0)).lower()}, "
                f"with {resource_condition_label(getattr(settlement, 'stored_resources', {}).get('food', 0.0)).lower()} supplies and "
                f"{security_label(getattr(settlement, 'security_level', 0.0)).lower()} protection."
            )
            status_tags = (
                stability_label(getattr(settlement, 'stability', 0.0)),
                security_label(getattr(settlement, 'security_level', 0.0)),
                resource_condition_label(getattr(settlement, 'stored_resources', {}).get('food', 0.0)),
            )
            if getattr(settlement, 'polity_id', None):
                affordances.append("Inspect associated polity")
        sections.append(_lines_to_section("identity", lines[:2]))
        sections.append(_lines_to_section("structured detail", lines[2:] + causes))
    elif prefix == "polity":
        polity = world.entity_by_ref(ref)
        lines = player_grade_polity_summary(world, ref)
        causes = player_grade_polity_recent_factors(world, ref)
        if polity is not None:
            summary = (
                f"{getattr(polity, 'name', ref)} currently reads as {power_label(getattr(polity, 'administrative_reach', 0.0)).lower()}, "
                f"with command integrity and war posture shaping how far its will truly reaches."
            )
            status_tags = (
                power_label(getattr(polity, 'administrative_reach', 0.0)),
                stability_label(getattr(polity, 'stability', 0.0)),
                security_label(getattr(polity, 'war_readiness', 0.0)),
            )
        sections.append(_lines_to_section("identity", lines[:2]))
        sections.append(_lines_to_section("structured detail", lines[2:] + causes))
        affordances.extend(["Pin to timeline", "Open event chain"])
    elif prefix == "war":
        lines = player_grade_war_summary(world, ref)
        causes = player_grade_war_recent_factors(world, ref)
        summary = "This conflict is moving through visible support, fatigue, and supply pressure rather than through one decisive number."
        status_tags = ("conflict", "volatile")
        sections.append(_lines_to_section("identity", lines[:2]))
        sections.append(_lines_to_section("structured detail", lines[2:] + causes))
        affordances.extend(["Show on timeline", "Inspect associated polity"])
    else:
        lines, summary, status_tags = _tile_overview(world, ref)
        sections.append(_lines_to_section("identity", lines[:2]))
        sections.append(_lines_to_section("structured detail", lines[2:]))
        affordances.extend(["Show related settlement", "Show local event chain"])

    sections.insert(1, _lines_to_section("situational summary", [summary]))
    sections.append(_lines_to_section("knowledge boundary", _knowledge_lines(world, ref), visibility=visibility_for_ref(world, ref)))

    if debug_mode:
        debug_lines = [line for line in debug_grade_step_report(world, max(0, world.current_step - 1)) if ref in line][:12]
        if debug_lines:
            sections.append(_lines_to_section("debug", debug_lines, visibility="confirmed"))

    return InspectionPanelProjection(
        ref=ref,
        title=f"{schema.title} {ref}",
        entity_kind=schema.entity_kind,
        status_tags=status_tags,
        summary=summary,
        sections=tuple(sections),
        affordances=tuple(dict.fromkeys(affordances)),
        debug_mode=debug_mode,
    )
