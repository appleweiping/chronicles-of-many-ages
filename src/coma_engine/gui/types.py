from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


VisibilityKind = Literal["confirmed", "inferred", "rumored", "hidden"]
MapMode = Literal["world", "control", "resources", "pressure", "infoflow"]


@dataclass(slots=True, frozen=True)
class TimeStateProjection:
    step: int
    phase_order: tuple[str, ...]
    completed_phases: tuple[str, ...]
    current_phase_label: str


@dataclass(slots=True, frozen=True)
class TileRenderProjection:
    ref: str
    x: int
    y: int
    terrain_type: str
    settlement_id: str | None
    controller_faction_id: str | None
    controller_polity_id: str | None
    effective_yield_total: float
    control_pressure: float
    local_unrest: float
    visibility_strength: float
    resident_count: int
    resource_stock_total: float
    activity_level: float
    attention_score: float
    attention_band: Literal["calm", "watch", "urgent", "critical"]
    attention_tags: tuple[str, ...]
    known_visibility: VisibilityKind
    power_level: float
    signal_level: float
    scarcity_level: float
    command_stress_level: float


@dataclass(slots=True, frozen=True)
class EntityCardProjection:
    ref: str
    label: str
    entity_kind: str
    location_ref: str | None
    related_refs: tuple[str, ...]
    visibility: VisibilityKind


@dataclass(slots=True, frozen=True)
class TimelineEntryProjection:
    event_id: str
    event_type: str
    step: int
    layer: str
    importance: float
    location_ref: str | None
    participant_refs: tuple[str, ...]
    cause_refs: tuple[str, ...]
    outcome_summary_code: str
    visibility: VisibilityKind


@dataclass(slots=True, frozen=True)
class InfoFlowProjection:
    packet_id: str
    content_domain: str
    subject_ref: str | None
    location_ref: str | None
    source_event_id: str | None
    strength: float
    distortion: float
    visibility_scope: str
    propagation_channels: tuple[str, ...]
    delivered_to: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class InspectionFieldProjection:
    key: str
    label: str
    value: str
    visibility: VisibilityKind


@dataclass(slots=True, frozen=True)
class InspectionSectionProjection:
    title: str
    fields: tuple[InspectionFieldProjection, ...]


@dataclass(slots=True, frozen=True)
class InspectionPanelProjection:
    ref: str
    title: str
    entity_kind: str
    status_tags: tuple[str, ...]
    summary: str
    sections: tuple[InspectionSectionProjection, ...]
    affordances: tuple[str, ...]
    debug_mode: bool = False


@dataclass(slots=True, frozen=True)
class InterventionOptionProjection:
    action_id: str
    label: str
    description: str
    target_ref: str
    channel: Literal["modifier", "info_packet", "event"]
    enabled: bool
    impact_hint: str = ""
    emphasis: Literal["support", "info", "mystic", "stabilize"] = "support"
    preview_lines: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class GuidanceItemProjection:
    title: str
    detail: str
    target_ref: str | None
    severity: Literal["critical", "warning", "opportunity", "rumor"]
    suggested_action_id: str | None
    visibility: VisibilityKind


@dataclass(slots=True, frozen=True)
class GuidanceSectionProjection:
    title: str
    items: tuple[GuidanceItemProjection, ...]


@dataclass(slots=True, frozen=True)
class AlertItemProjection:
    title: str
    detail: str
    target_ref: str | None
    severity: Literal["critical", "major", "notable"]
    related_timeline_event_id: str | None
    suggested_map_mode: MapMode
    visibility: VisibilityKind


@dataclass(slots=True, frozen=True)
class ChronicleItemProjection:
    headline: str
    detail: str
    target_ref: str | None
    region_ref: str | None
    tone: Literal["regional", "civilization", "rumor"]


@dataclass(slots=True, frozen=True)
class TimelineRowProjection:
    headline: str
    detail: str
    target_ref: str | None
    tone: Literal["major", "notable", "rumor"]


@dataclass(slots=True, frozen=True)
class TimelineGroupProjection:
    title: str
    rows: tuple[TimelineRowProjection, ...]


@dataclass(slots=True, frozen=True)
class WorldStatusProjection:
    headline: str
    summary_lines: tuple[str, ...]
    attention_count: int
    opportunity_count: int


@dataclass(slots=True, frozen=True)
class TopBarProjection:
    scenario_name: str
    step_label: str
    time_state_label: str
    speed_label: str
    influence_label: str
    visibility_label: str
    objective_label: str
    atmosphere_labels: tuple[str, ...]


@dataclass(slots=True, frozen=True)
class WorldFrameProjection:
    time_state: TimeStateProjection
    tiles: tuple[TileRenderProjection, ...]
    entity_cards: tuple[EntityCardProjection, ...]
    timeline_entries: tuple[TimelineEntryProjection, ...]
    info_flows: tuple[InfoFlowProjection, ...]
    overlay_defaults: tuple[str, ...] = ("terrain", "power", "attention", "signals")


@dataclass(slots=True)
class GuiViewState:
    selected_ref: str | None = None
    zoom_level: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    debug_mode: bool = False
    running: bool = False
    speed_mode: Literal["paused", "normal", "burst"] = "paused"
    current_map_mode: MapMode = "world"
    active_overlays: set[str] = field(default_factory=lambda: {"terrain", "power", "attention", "signals"})
    selected_action_id: str | None = None
    selected_action_target_ref: str | None = None
    selection_history: list[str] = field(default_factory=list)
