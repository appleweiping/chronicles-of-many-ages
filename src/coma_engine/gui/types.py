from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


VisibilityKind = Literal["confirmed", "inferred", "rumored", "hidden"]


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
    sections: tuple[InspectionSectionProjection, ...]
    debug_mode: bool = False


@dataclass(slots=True, frozen=True)
class InterventionOptionProjection:
    action_id: str
    label: str
    description: str
    target_ref: str
    channel: Literal["modifier", "info_packet", "event"]
    enabled: bool


@dataclass(slots=True, frozen=True)
class WorldFrameProjection:
    time_state: TimeStateProjection
    tiles: tuple[TileRenderProjection, ...]
    entity_cards: tuple[EntityCardProjection, ...]
    timeline_entries: tuple[TimelineEntryProjection, ...]
    info_flows: tuple[InfoFlowProjection, ...]
    overlay_defaults: tuple[str, ...] = ("terrain", "control", "activity")


@dataclass(slots=True)
class GuiViewState:
    selected_ref: str | None = None
    zoom_level: float = 1.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    debug_mode: bool = False
    running: bool = False
    active_overlays: set[str] = field(default_factory=lambda: {"terrain", "control", "activity"})
