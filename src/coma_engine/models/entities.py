from __future__ import annotations

from dataclasses import dataclass, field

from coma_engine.models.perception import PerceivedState


ResourceBundle = dict[str, float]


@dataclass(slots=True)
class RelationEntry:
    affinity: float = 0.0
    trust: float = 0.0
    fear: float = 0.0
    debt: float = 0.0
    grievance: float = 0.0
    familiarity: float = 0.0


@dataclass(slots=True)
class Goal:
    goal_type: str
    target_ref: str | None = None
    threshold: float | None = None


@dataclass(slots=True)
class Objective:
    id: str
    objective_type: str
    target_ref: str | None
    threshold: float
    duration_requirement: int
    progress_metric: str
    failure_conditions: list[str]
    visibility_policy: str
    progress: float = 0.0
    maintained_steps: int = 0
    failed: bool = False
    completed: bool = False


@dataclass(slots=True)
class Tile:
    id: str
    x: int
    y: int
    terrain_type: str
    base_yield: ResourceBundle
    current_stock: ResourceBundle
    fertility: float
    danger: float
    capacity: float
    tags: list[str] = field(default_factory=list)
    settlement_id: str | None = None
    controller_faction_id: str | None = None
    controller_polity_id: str | None = None
    resident_npc_ids: list[str] = field(default_factory=list)
    adjacent_tile_ids: list[str] = field(default_factory=list)
    active_modifier_ids: list[str] = field(default_factory=list)
    effective_yield: ResourceBundle = field(default_factory=dict)
    effective_path_cost: float = 1.0
    effective_control_pressure: float = 0.0
    effective_visibility: float = 1.0
    local_unrest: float = 0.0
    taxable_output_estimate: float = 0.0


@dataclass(slots=True)
class NPC:
    id: str
    name: str
    alive: bool
    age: float
    culture_id: str
    family_id: str
    location_tile_id: str
    health: float
    settlement_id: str | None
    faction_id: str | None
    polity_id: str | None
    role: str
    office_rank: int
    personal_inventory: ResourceBundle
    needs: dict[str, float]
    personality: dict[str, float]
    abilities: dict[str, float]
    beliefs: dict[str, float]
    relationships: dict[str, RelationEntry]
    memory_ids: list[str]
    long_term_goal: Goal
    active_modifier_ids: list[str]
    cooldowns: dict[str, int]
    current_action_ref: str | None
    perceived_state: PerceivedState
    salience_scores: dict[str, float] = field(default_factory=dict)
    effective_need_weights: dict[str, float] = field(default_factory=dict)
    candidate_actions: list[str] = field(default_factory=list)
    action_score_breakdown: dict[str, dict[str, float]] = field(default_factory=dict)
    local_priority_map: dict[str, float] = field(default_factory=dict)
    effective_risk_profile: float = 0.0
    effective_loyalty_conflict: float = 0.0


@dataclass(slots=True)
class Settlement:
    id: str
    name: str
    core_tile_id: str
    member_tile_ids: list[str]
    resident_npc_ids: list[str]
    stored_resources: ResourceBundle
    security_level: float
    stability: float
    faction_id: str | None
    polity_id: str | None
    active_modifier_ids: list[str]
    labor_pool: float = 0.0
    net_production: ResourceBundle = field(default_factory=dict)
    current_taxable_output: float = 0.0
    migration_pressure: float = 0.0
    effective_trade_value: float = 0.0
    effective_security_risk: float = 0.0


@dataclass(slots=True)
class Faction:
    id: str
    name: str
    leader_npc_id: str
    member_npc_ids: list[str]
    settlement_ids: list[str]
    support_score: float
    cohesion: float
    agenda_type: str
    legitimacy_seed_components: dict[str, float]
    active_modifier_ids: list[str]
    coup_readiness: float = 0.0
    effective_support_network: float = 0.0
    regional_influence: float = 0.0
    mobilization_capacity: float = 0.0


@dataclass(slots=True)
class Polity:
    id: str
    name: str
    capital_settlement_id: str
    ruling_faction_id: str
    ruler_npc_id: str
    member_settlement_ids: list[str]
    member_faction_ids: list[str]
    treasury: ResourceBundle
    administrative_reach: float
    legitimacy_components: dict[str, float]
    stability: float
    military_strength_base: float
    external_relations: dict[str, float]
    active_modifier_ids: list[str]
    command_network_state: dict[str, float]
    effective_military_strength: float = 0.0
    tax_leakage_rate: float = 0.0
    frontier_tension: float = 0.0
    effective_population_control: float = 0.0
    war_readiness: float = 0.0


@dataclass(slots=True)
class WarState:
    id: str
    participant_polity_ids: list[str]
    participant_faction_ids: list[str]
    start_step: int
    war_type: str
    front_regions: list[str]
    war_support_levels: dict[str, float]
    war_fatigue_levels: dict[str, float]
    mobilization_modifiers: list[str]
    tax_modifiers: list[str]
    propagation_modifiers: list[str]
    legitimacy_effect_direction: float
    status: str
    effective_front_pressure: float = 0.0
    expected_attrition: float = 0.0
    escalation_risk: float = 0.0


@dataclass(slots=True)
class Event:
    id: str
    event_type: str
    timestamp_step: int
    location_tile_id: str | None
    region_ref: str | None
    participant_ids: list[str]
    cause_refs: list[str]
    outcome_summary_code: str
    importance: float
    visibility_scope: str
    derived_memory_ids: list[str]
    derived_modifier_ids: list[str]
    derived_info_packet_ids: list[str]
    archived: bool = False


@dataclass(slots=True)
class MemoryEntry:
    id: str
    npc_id: str
    source_event_id: str
    impression_strength: float
    emotion_tag: str
    decay_rate: float
    bias_conversion_rule: str
    created_step: int
    current_effect_weight: float = 0.0
    is_conversion_ready: bool = False


@dataclass(slots=True)
class InfoPacket:
    id: str
    source_event_id: str | None
    origin_actor_id: str | None
    content_domain: str
    subject_ref: str | None
    location_ref: str | None
    strength: float
    distortion: float
    visibility_scope: str
    remaining_ttl: int
    propagation_channels: list[str]
    truth_alignment: float
    created_step: int
    propagated_this_step: bool = False


@dataclass(slots=True)
class Modifier:
    id: str
    modifier_type: str
    mode: str
    target_ref: str
    domain: str
    magnitude: float
    duration_remaining: int
    stacking_rule: str
    priority: int
    source_ref: str | None
    trigger_rule: str | None
    inactive: bool = False


@dataclass(slots=True)
class PlayerState:
    influence_points: float = 0.0
    visibility_level: float = 0.0
    known_entities: set[str] = field(default_factory=set)
    known_regions: set[str] = field(default_factory=set)
    active_objectives: list[Objective] = field(default_factory=list)
    cooldowns: dict[str, int] = field(default_factory=dict)
    intervention_history: list[str] = field(default_factory=list)
