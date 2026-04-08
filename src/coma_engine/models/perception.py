from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ThreatPerception:
    subject_ref: str
    location_ref: str | None
    threat_strength: float
    source_ref: str
    credibility: float
    expires_step: int


@dataclass(slots=True)
class OpportunityPerception:
    subject_ref: str
    location_ref: str | None
    opportunity_kind: str
    estimated_benefit: float
    source_ref: str
    credibility: float
    expires_step: int


@dataclass(slots=True)
class RelationShiftPerception:
    subject_ref: str
    summary_code: str
    delta_strength: float
    source_ref: str
    credibility: float
    expires_step: int


@dataclass(slots=True)
class PowerMapPerception:
    subject_ref: str
    power_score: float
    rank_hint: int
    source_ref: str
    credibility: float
    expires_step: int


@dataclass(slots=True)
class ResourceSignalPerception:
    location_ref: str
    resource_type: str
    abundance_signal: float
    source_ref: str
    credibility: float
    expires_step: int


@dataclass(slots=True)
class BeliefSignalPerception:
    belief_domain: str
    signal_strength: float
    source_ref: str
    credibility: float
    expires_step: int


@dataclass(slots=True)
class RecentEventPerception:
    event_id: str
    summary_code: str
    importance: float
    source_ref: str
    credibility: float
    expires_step: int


@dataclass(slots=True)
class PerceivedState:
    perceived_threats: list[ThreatPerception] = field(default_factory=list)
    perceived_opportunities: list[OpportunityPerception] = field(default_factory=list)
    perceived_relations_shift: list[RelationShiftPerception] = field(default_factory=list)
    perceived_power_map: list[PowerMapPerception] = field(default_factory=list)
    perceived_resource_signals: list[ResourceSignalPerception] = field(default_factory=list)
    perceived_belief_signals: list[BeliefSignalPerception] = field(default_factory=list)
    perceived_recent_events: list[RecentEventPerception] = field(default_factory=list)

    def prune(self, current_step: int) -> None:
        for channel_name in (
            "perceived_threats",
            "perceived_opportunities",
            "perceived_relations_shift",
            "perceived_power_map",
            "perceived_resource_signals",
            "perceived_belief_signals",
            "perceived_recent_events",
        ):
            channel = getattr(self, channel_name)
            setattr(
                self,
                channel_name,
                [entry for entry in channel if entry.expires_step >= current_step],
            )
