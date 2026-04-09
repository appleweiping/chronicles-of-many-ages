from __future__ import annotations

from coma_engine.core.state import WorldState
from coma_engine.gui.presentation.labels import (
    command_integrity_label,
    conflict_density_label,
    consolidation_label,
    harvest_label,
    rumor_activity_label,
    unrest_trend_label,
    visibility_label,
)
from coma_engine.gui.types import AlertItemProjection, ChronicleItemProjection, TopBarProjection, WorldFrameProjection, WorldStatusProjection


def _humanize(code: str) -> str:
    return code.replace("_", " ").title()


def _pick_target(location_ref: str | None, participant_refs: tuple[str, ...]) -> str | None:
    if location_ref:
        return location_ref
    return participant_refs[0] if participant_refs else None


def _severity_for_entry(importance: float, event_type: str) -> str:
    critical_terms = ("COLLAPSE", "FAMINE", "COUP", "RULER_DEATH", "WAR_ESCALATED", "COMMAND_FAILURE", "MIRACLE")
    if importance >= 82.0 or any(term in event_type for term in critical_terms):
        return "critical"
    if importance >= 62.0:
        return "major"
    return "notable"


def _mode_for_entry(event_type: str) -> str:
    if "WAR" in event_type or "COMMAND" in event_type:
        return "pressure"
    if "RUMOR" in event_type or "BELIEF" in event_type:
        return "infoflow"
    if "RESOURCE" in event_type or "HARVEST" in event_type:
        return "resources"
    if "POLITY" in event_type or "FACTION" in event_type:
        return "control"
    return "world"


def build_alert_stack(world: WorldState, frame: WorldFrameProjection, limit: int = 8) -> tuple[AlertItemProjection, ...]:
    alerts: list[AlertItemProjection] = []
    for entry in frame.timeline_entries:
        if entry.visibility == "hidden":
            continue
        severity = _severity_for_entry(entry.importance, entry.event_type)
        if severity == "notable" and entry.importance < 48.0:
            continue
        alerts.append(
            AlertItemProjection(
                title=_humanize(entry.event_type),
                detail=f"Step {entry.step} · {_humanize(entry.outcome_summary_code)}",
                target_ref=_pick_target(entry.location_ref, entry.participant_refs),
                severity=severity,
                related_timeline_event_id=entry.event_id,
                suggested_map_mode=_mode_for_entry(entry.event_type),
                visibility=entry.visibility,
            )
        )
    existing_targets = {alert.target_ref for alert in alerts if alert.target_ref is not None}
    for tile in sorted(
        frame.tiles,
        key=lambda item: (item.change_intensity + item.attention_score * 0.22 + max(0.0, item.pressure_delta) * 0.7),
        reverse=True,
    ):
        if tile.known_visibility == "hidden" or tile.ref in existing_targets:
            continue
        if tile.attention_score < 26.0 and tile.change_intensity < 8.0 and tile.command_stress_level < 28.0:
            continue
        if tile.pressure_delta >= 6.0 or tile.change_direction == "rising":
            title = f"Instability Rising At {tile.ref}"
            detail = ", ".join(tile.attention_tags[:3])
            severity = "critical" if tile.command_stress_level >= 55.0 else "major"
            mode = "pressure"
        elif tile.signal_delta >= 4.0 or tile.signal_level >= 12.0:
            title = f"Signals Spreading Near {tile.ref}"
            detail = ", ".join(tile.attention_tags[:3])
            severity = "major" if tile.signal_level >= 16.0 else "notable"
            mode = "infoflow"
        elif tile.change_direction == "falling" and tile.command_stress_level < 32.0:
            title = f"Conditions Easing Near {tile.ref}"
            detail = ", ".join(tile.attention_tags[:2])
            severity = "notable"
            mode = "world"
        else:
            title = f"Hotspot At {tile.ref}"
            detail = ", ".join(tile.attention_tags[:2])
            severity = "major" if tile.attention_band in {"urgent", "critical"} else "notable"
            mode = "pressure" if tile.command_stress_level >= tile.scarcity_level else "world"
        alerts.append(
            AlertItemProjection(
                title=title,
                detail=detail,
                target_ref=tile.ref,
                severity=severity,
                related_timeline_event_id=None,
                suggested_map_mode=mode,
                visibility=tile.known_visibility,
            )
        )
        if len(alerts) >= limit:
            break
    if not alerts:
        alerts.append(
            AlertItemProjection(
                title=f"Watch {world.current_step}",
                detail="No major tensions are visible yet, but the world is still shifting.",
                target_ref=frame.tiles[0].ref if frame.tiles else None,
                severity="notable",
                related_timeline_event_id=None,
                suggested_map_mode="world",
                visibility="confirmed",
            )
        )
    return tuple(alerts[:limit])


def build_chronicle_stream(world: WorldState, frame: WorldFrameProjection, limit: int = 10) -> tuple[ChronicleItemProjection, ...]:
    del world
    grouped: dict[tuple[str, str], list[object]] = {}
    for entry in frame.timeline_entries:
        if entry.importance >= 70.0:
            continue
        region_ref = entry.location_ref or "unknown"
        theme = "rumor" if entry.visibility in {"rumored", "inferred"} else entry.layer
        grouped.setdefault((region_ref, theme), []).append(entry)

    chronicle: list[ChronicleItemProjection] = []
    for (region_ref, theme), entries in list(grouped.items())[:limit]:
        latest = entries[0]
        if theme == "rumor":
            headline = f"Whispers continue around {region_ref}"
            detail = f"{len(entries)} low-visibility developments are circulating through this region."
            tone = "rumor"
        elif theme == "local_chronicle":
            headline = f"Pressure keeps shifting near {region_ref}"
            detail = f"{len(entries)} connected local developments continue to reshape nearby settlements."
            tone = "regional"
        else:
            headline = f"Broader change touches {region_ref}"
            detail = f"{len(entries)} linked developments now connect to larger political movement."
            tone = "civilization"
        chronicle.append(
            ChronicleItemProjection(
                headline=headline,
                detail=detail,
                target_ref=_pick_target(latest.location_ref, latest.participant_refs),
                region_ref=region_ref if isinstance(region_ref, str) else None,
                tone=tone,
            )
        )
    return tuple(chronicle[:limit])


def build_top_bar(world: WorldState, frame: WorldFrameProjection, view_state) -> TopBarProjection:
    avg_yield = sum(tile.effective_yield_total for tile in frame.tiles) / max(1, len(frame.tiles))
    avg_unrest = sum(tile.local_unrest for tile in frame.tiles) / max(1, len(frame.tiles))
    avg_power = sum(tile.power_level for tile in frame.tiles) / max(1, len(frame.tiles))
    polities = list(world.polities.values())
    avg_integrity = sum(polity.command_network_state.get("integrity", 0.0) for polity in polities) / max(1, len(polities))
    objective_label = "No active objective"
    if world.player_state.active_objectives:
        objective = world.player_state.active_objectives[0]
        objective_label = f"{objective.objective_type}: {objective.progress:.0f}/{objective.threshold:.0f}"
    speed_label = "Paused" if not view_state.running else ("Burst" if view_state.speed_mode == "burst" else "Running")
    return TopBarProjection(
        scenario_name="Base Chronicle",
        step_label=f"Step {frame.time_state.step}",
        time_state_label=frame.time_state.current_phase_label,
        speed_label=speed_label,
        influence_label=f"Influence {world.player_state.influence_points:.0f}",
        visibility_label=f"Visibility {visibility_label(world.player_state.visibility_level)}",
        objective_label=objective_label,
        atmosphere_labels=(
            harvest_label(avg_yield),
            unrest_trend_label(avg_unrest),
            conflict_density_label(world),
            rumor_activity_label(sum(1 for flow in frame.info_flows if flow.location_ref)),
            command_integrity_label(avg_integrity),
            consolidation_label(avg_power),
        ),
    )


def build_world_status(world: WorldState, frame: WorldFrameProjection) -> WorldStatusProjection:
    alerts = sum(1 for tile in frame.tiles if tile.attention_band in {"urgent", "critical"} and tile.known_visibility == "confirmed")
    headline = f"Hotspots {alerts} · Wars {len([war for war in world.war_states.values() if war.status == 'active'])}"
    summary_lines = (
        f"Known entities {len(world.player_state.known_entities)} · regions {len(world.player_state.known_regions)}",
        f"Signals visible {sum(1 for flow in frame.info_flows if flow.location_ref)} · phase trace {frame.time_state.current_phase_label}",
    )
    return WorldStatusProjection(headline=headline, summary_lines=summary_lines, attention_count=alerts, opportunity_count=0)


def pick_default_focus_ref(frame: WorldFrameProjection, alerts: tuple[AlertItemProjection, ...]) -> str | None:
    for item in alerts:
        if item.target_ref is not None:
            return item.target_ref
    return frame.tiles[0].ref if frame.tiles else None
