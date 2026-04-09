from __future__ import annotations

from coma_engine.core.state import WorldState


def band_label(value: float, *, low: str, mid: str, high: str) -> str:
    if value >= 68.0:
        return high
    if value >= 38.0:
        return mid
    return low


def visibility_label(value: float) -> str:
    return band_label(value, low="Obscured", mid="Partial", high="Broad")


def resource_condition_label(value: float) -> str:
    return band_label(value, low="Thin", mid="Uneven", high="Secure")


def stability_label(value: float) -> str:
    return band_label(value, low="Fragile", mid="Uneasy", high="Steady")


def security_label(value: float) -> str:
    return band_label(value, low="Exposed", mid="Watchful", high="Guarded")


def power_label(value: float) -> str:
    return band_label(value, low="Peripheral", mid="Contested", high="Consolidated")


def conflict_density_label(world: WorldState) -> str:
    active_wars = len([war for war in world.war_states.values() if war.status == "active"])
    if active_wars >= 3:
        return "Multiple Conflicts Detected"
    if active_wars >= 1:
        return "Conflict Pressure Present"
    return "No Major Wars Visible"


def rumor_activity_label(signal_count: int) -> str:
    if signal_count >= 12:
        return "Rumor Activity High"
    if signal_count >= 5:
        return "Rumor Activity Rising"
    return "Rumor Activity Mild"


def command_integrity_label(avg_integrity: float) -> str:
    if avg_integrity < 42.0:
        return "Command Integrity Weak"
    if avg_integrity < 68.0:
        return "Command Integrity Uneven"
    return "Command Integrity Holding"


def harvest_label(avg_yield: float) -> str:
    if avg_yield < 8.0:
        return "Harvest Weak"
    if avg_yield < 14.0:
        return "Harvest Uneven"
    return "Harvest Stable"


def unrest_trend_label(avg_unrest: float) -> str:
    if avg_unrest >= 55.0:
        return "Local Instability Rising"
    if avg_unrest >= 28.0:
        return "Local Friction Visible"
    return "Local Order Holding"


def consolidation_label(avg_power: float) -> str:
    if avg_power >= 45.0:
        return "Regional Power Consolidating"
    if avg_power >= 24.0:
        return "Regional Power Contesting"
    return "Regional Power Diffuse"
