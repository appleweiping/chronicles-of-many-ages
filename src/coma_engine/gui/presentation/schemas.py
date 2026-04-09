from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class InspectionSchema:
    entity_kind: str
    title: str
    section_order: tuple[str, ...]


SCHEMA_REGISTRY: dict[str, InspectionSchema] = {
    "tile": InspectionSchema("tile", "Region", ("at a glance", "what you know")),
    "npc": InspectionSchema("npc", "Figure", ("at a glance", "what you know")),
    "settlement": InspectionSchema("settlement", "Settlement", ("at a glance", "what is happening", "what you know")),
    "faction": InspectionSchema("faction", "Faction", ("at a glance", "what you know")),
    "polity": InspectionSchema("polity", "Polity", ("power and order", "pressure points", "what you know")),
    "war": InspectionSchema("war", "War", ("war state", "why it is shifting", "what you know")),
}
