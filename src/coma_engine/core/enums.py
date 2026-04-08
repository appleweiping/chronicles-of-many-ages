from __future__ import annotations

from enum import StrEnum


class PhaseName(StrEnum):
    ENVIRONMENT = "EnvironmentPhase"
    RESOURCE = "ResourcePhase"
    NEED_UPDATE = "NeedUpdatePhase"
    INFORMATION = "InformationPhase"
    DECISION = "DecisionPhase"
    DECLARATION = "DeclarationPhase"
    RESOLUTION = "ResolutionPhase"
    POLITICAL = "PoliticalPhase"
    EVENT = "EventPhase"


class ModifierMode(StrEnum):
    GATING = "gating"
    OVERRIDE = "override"
    ADDITIVE = "additive"
    MULTIPLICATIVE = "multiplicative"
    TRIGGERED = "triggered"


class ActionStatus(StrEnum):
    DECLARED = "declared"
    RESERVED = "reserved"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"


class DurationType(StrEnum):
    INSTANT = "instant"
    TRAVEL = "travel"
    CHANNELING = "channeling"
    CAMPAIGN = "campaign"
    SCHEME = "scheme"


class PriorityClass(StrEnum):
    SURVIVAL = "survival"
    CIVIC = "civic"
    POLITICAL = "political"
    WAR = "war"


class GoalType(StrEnum):
    SURVIVE = "SURVIVE"
    SECURE_FAMILY = "SECURE_FAMILY"
    GAIN_WEALTH = "GAIN_WEALTH"
    GAIN_STATUS = "GAIN_STATUS"
    EXPAND_FACTION = "EXPAND_FACTION"
    FOUND_POLITY = "FOUND_POLITY"
    REVENGE_TARGET = "REVENGE_TARGET"
    PRESERVE_GROUP = "PRESERVE_GROUP"
    CONTROL_REGION = "CONTROL_REGION"
    MAINTAIN_ORDER = "MAINTAIN_ORDER"


class HistoricalLayer(StrEnum):
    RAW_EVENT = "raw_event"
    LOCAL_CHRONICLE = "local_chronicle"
    CIVILIZATION_NODE = "civilization_node"
