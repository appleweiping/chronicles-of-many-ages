from __future__ import annotations

from collections.abc import Iterable

from coma_engine.core.state import WorldState


def active_modifiers_for(world: WorldState, target_ref: str, domain: str) -> list:
    modifiers = [
        modifier
        for modifier in world.modifiers.values()
        if not modifier.inactive
        and modifier.target_ref == target_ref
        and modifier.domain == domain
        and modifier.duration_remaining > 0
    ]
    return sorted(modifiers, key=lambda item: (item.priority, item.id))


def apply_modifier_pipeline(
    base_value: float,
    modifiers: Iterable,
) -> tuple[bool, float, list[str]]:
    allowed = True
    value = base_value
    triggered_rules: list[str] = []
    grouped = {"gating": [], "override": [], "additive": [], "multiplicative": [], "triggered": []}
    for modifier in modifiers:
        grouped[modifier.mode].append(modifier)

    for modifier in grouped["gating"]:
        if modifier.magnitude <= 0:
            allowed = False
    if not allowed:
        return False, 0.0, triggered_rules

    if grouped["override"]:
        value = grouped["override"][-1].magnitude

    for modifier in grouped["additive"]:
        value += modifier.magnitude

    for modifier in grouped["multiplicative"]:
        value *= 1.0 + modifier.magnitude

    for modifier in grouped["triggered"]:
        if modifier.trigger_rule:
            triggered_rules.append(modifier.trigger_rule)

    return allowed, value, triggered_rules


def tick_modifier_lifecycles(world: WorldState) -> None:
    for modifier in world.modifiers.values():
        if modifier.duration_remaining > 0:
            modifier.duration_remaining -= 1
        if modifier.duration_remaining <= 0:
            modifier.inactive = True
