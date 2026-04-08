from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Action:
    id: str
    action_type: str
    actor_id: str
    target_npc_id: str | None
    target_tile_id: str | None
    target_settlement_id: str | None
    target_faction_id: str | None
    target_polity_id: str | None
    declared_step: int
    priority_class: str
    duration_type: str
    estimated_duration: int
    resource_cost: dict[str, float]
    risk_value: float
    availability_rule_id: str
    resolution_group_key: str
    status: str


@dataclass(slots=True)
class TargetSignature:
    required_targets: tuple[str, ...] = ()
    optional_targets: tuple[str, ...] = ()
    forbidden_targets: tuple[str, ...] = ()
    allow_targetless: bool = False


@dataclass(slots=True)
class ContestScore:
    ability_component: float = 0.0
    support_component: float = 0.0
    position_component: float = 0.0
    modifier_component: float = 0.0
    noise_component: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.ability_component
            + self.support_component
            + self.position_component
            + self.modifier_component
            + self.noise_component
        )


@dataclass(slots=True)
class ActionOutcome:
    action_id: str
    action_type: str
    actor_id: str
    result: str
    summary_code: str
    participant_ids: list[str]
    cause_refs: list[str]
    target_refs: list[str]
    resource_delta: dict[str, float] = field(default_factory=dict)
    generated_modifier_ids: list[str] = field(default_factory=list)
    generated_info_packet_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AvailabilityDecision:
    allowed: bool
    reason_code: str


@dataclass(slots=True)
class ActionTemplate:
    action_type: str
    signature: TargetSignature
    default_priority_class: str
    default_duration_type: str
    default_duration: int
    availability_rule_id: str
