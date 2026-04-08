from __future__ import annotations

from dataclasses import dataclass, field

from coma_engine.config.schema import ConfigSchema


@dataclass(slots=True)
class ScenarioDefinition:
    name: str
    config_overrides: dict[str, object] = field(default_factory=dict)
    initial_objectives: list[dict[str, object]] = field(default_factory=list)
    lore_notes: list[str] = field(default_factory=list)


def apply_scenario_config(base_config: ConfigSchema, scenario: ScenarioDefinition) -> ConfigSchema:
    config = ConfigSchema(seed=base_config.seed)
    config.design_constants = base_config.design_constants
    config.balance_parameters = base_config.balance_parameters
    for key, value in scenario.config_overrides.items():
        if hasattr(config.balance_parameters, key):
            setattr(config.balance_parameters, key, value)
    return config
