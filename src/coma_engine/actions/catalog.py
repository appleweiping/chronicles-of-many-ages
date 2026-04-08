from __future__ import annotations

from coma_engine.actions.models import ActionTemplate, TargetSignature


ACTION_TEMPLATES: dict[str, ActionTemplate] = {
    "FORAGE": ActionTemplate(
        action_type="FORAGE",
        signature=TargetSignature(required_targets=("target_tile_id",)),
        default_priority_class="survival",
        default_duration_type="instant",
        default_duration=1,
        availability_rule_id="basic_survival",
    ),
    "MOVE": ActionTemplate(
        action_type="MOVE",
        signature=TargetSignature(required_targets=("target_tile_id",)),
        default_priority_class="survival",
        default_duration_type="travel",
        default_duration=1,
        availability_rule_id="movement",
    ),
    "FOUND_POLITY": ActionTemplate(
        action_type="FOUND_POLITY",
        signature=TargetSignature(required_targets=("target_settlement_id",)),
        default_priority_class="political",
        default_duration_type="scheme",
        default_duration=3,
        availability_rule_id="found_polity",
    ),
    "FORMAL_TAX_ORDER": ActionTemplate(
        action_type="FORMAL_TAX_ORDER",
        signature=TargetSignature(required_targets=("target_settlement_id",)),
        default_priority_class="civic",
        default_duration_type="instant",
        default_duration=1,
        availability_rule_id="formal_tax_order",
    ),
    "DECLARE_WAR": ActionTemplate(
        action_type="DECLARE_WAR",
        signature=TargetSignature(required_targets=("target_polity_id",)),
        default_priority_class="war",
        default_duration_type="instant",
        default_duration=1,
        availability_rule_id="declare_war",
    ),
}
