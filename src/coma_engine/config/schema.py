from __future__ import annotations

from dataclasses import dataclass, field


ResourceName = str
TerrainType = str


@dataclass(slots=True)
class DesignConstants:
    phase_order: tuple[str, ...] = (
        "EnvironmentPhase",
        "ResourcePhase",
        "NeedUpdatePhase",
        "InformationPhase",
        "DecisionPhase",
        "DeclarationPhase",
        "ResolutionPhase",
        "PoliticalPhase",
        "EventPhase",
    )
    resource_types: tuple[ResourceName, ...] = ("food", "wood", "ore", "wealth")
    tile_resource_types: tuple[ResourceName, ...] = ("food", "wood", "ore")
    resource_numeric_scheme: str = "float"
    adjacency_mode: str = "four_way"
    perceived_state_channels: tuple[str, ...] = (
        "perceived_threats",
        "perceived_opportunities",
        "perceived_relations_shift",
        "perceived_power_map",
        "perceived_resource_signals",
        "perceived_belief_signals",
        "perceived_recent_events",
    )
    modifier_pipeline: tuple[str, ...] = (
        "gating",
        "override",
        "additive",
        "multiplicative",
        "triggered",
    )
    relation_axes: tuple[str, ...] = (
        "affinity",
        "trust",
        "fear",
        "debt",
        "grievance",
        "familiarity",
    )
    goal_types: tuple[str, ...] = (
        "SURVIVE",
        "SECURE_FAMILY",
        "GAIN_WEALTH",
        "GAIN_STATUS",
        "EXPAND_FACTION",
        "FOUND_POLITY",
        "REVENGE_TARGET",
        "PRESERVE_GROUP",
        "CONTROL_REGION",
        "MAINTAIN_ORDER",
    )
    action_duration_types: tuple[str, ...] = (
        "instant",
        "travel",
        "channeling",
        "campaign",
        "scheme",
    )
    propagation_channels: tuple[str, ...] = ("spatial", "relationship", "organizational")
    phase_snapshot_retention: int = 9


@dataclass(slots=True)
class BalanceParameters:
    reference_long_run_steps: int = 24
    tile_regen_rate: float = 0.15
    food_need_decay: float = 8.0
    safety_need_decay: float = 2.0
    social_need_decay: float = 1.5
    status_need_decay: float = 1.0
    meaning_need_decay: float = 0.8
    forage_yield_factor: float = 0.65
    stock_consumption_per_npc: float = 1.0
    local_settlement_entry_population: int = 3
    local_settlement_exit_population: int = 1
    faction_entry_support: float = 58.0
    faction_exit_support: float = 42.0
    polity_entry_support: float = 68.0
    polity_exit_support: float = 48.0
    polity_entry_reach: float = 40.0
    polity_entry_stability: float = 50.0
    polity_exit_stability: float = 30.0
    command_base_ttl: int = 4
    rumor_base_ttl: int = 3
    default_perception_ttl: int = 4
    perception_channel_capacity: int = 6
    debug_candidate_action_count: int = 5
    action_noise_amplitude: float = 3.0
    low_rank_high_politics_gate_rank: int = 3
    labor_age_min: int = 16
    labor_age_max: int = 60
    combat_age_min: int = 16
    combat_age_max: int = 45
    age_increment_per_step: float = 1.0
    base_mortality_probability: float = 0.002
    old_age_start: float = 65.0
    old_age_mortality_scale: float = 0.003
    birth_food_threshold: float = 10.0
    settlement_birth_probability: float = 0.08
    war_attrition_scale: float = 0.06
    peace_tension_gain: float = 0.8
    war_strain_decay: float = 0.6
    war_loot_rate: float = 0.08
    belief_signal_amplifier_scale: float = 0.5
    memory_conversion_threshold: float = 6.0
    command_skim_base_rate: float = 0.18
    command_resistance_threshold: float = 35.0
    command_skimming_threshold: float = 55.0
    command_skimming_integrity_penalty: float = 14.0
    command_skimming_civil_order_penalty: float = 9.0
    command_local_retention_stability_gain: float = 4.0
    command_compliance_civil_order_gain: float = 2.5
    command_resistance_integrity_penalty: float = 7.0
    loot_remittance_rate: float = 0.55
    relation_templates: dict[str, dict[str, float]] = field(
        default_factory=lambda: {
            "aid": {"debt": 12.0, "trust": 10.0, "affinity": 4.0},
            "betrayal": {"trust": -20.0, "grievance": 18.0, "fear": 8.0},
            "shared_work": {"familiarity": 5.0, "trust": 2.0},
            "repression": {"fear": 16.0, "grievance": 14.0},
            "good_governance": {"trust": 6.0, "affinity": 4.0},
            "extractive_taxation": {"grievance": 10.0, "affinity": -5.0},
        }
    )
    path_costs: dict[TerrainType, float] = field(
        default_factory=lambda: {
            "plains": 1.0,
            "forest": 1.5,
            "hill": 2.0,
            "mountain": 3.0,
            "water": 9999.0,
        }
    )
    terrain_yields: dict[TerrainType, dict[ResourceName, float]] = field(
        default_factory=lambda: {
            "plains": {"food": 3.0, "wood": 0.5, "ore": 0.2},
            "forest": {"food": 1.5, "wood": 3.0, "ore": 0.3},
            "hill": {"food": 1.2, "wood": 1.0, "ore": 1.8},
            "mountain": {"food": 0.4, "wood": 0.3, "ore": 3.2},
            "water": {"food": 0.0, "wood": 0.0, "ore": 0.0},
        }
    )
    world_width: int = 8
    world_height: int = 8
    initial_population: int = 18
    initial_culture_count: int = 3
    initial_family_count: int = 6


@dataclass(slots=True)
class ConfigSchema:
    seed: int = 7
    design_constants: DesignConstants = field(default_factory=DesignConstants)
    balance_parameters: BalanceParameters = field(default_factory=BalanceParameters)


def default_config(seed: int = 7) -> ConfigSchema:
    return ConfigSchema(seed=seed)
