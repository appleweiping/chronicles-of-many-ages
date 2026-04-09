from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class InspectionSchema:
    entity_kind: str
    title: str
    section_order: tuple[str, ...]


SCHEMA_REGISTRY: dict[str, InspectionSchema] = {
    "tile": InspectionSchema("tile", "Tile", ("overview", "activity", "visibility")),
    "npc": InspectionSchema("npc", "NPC", ("overview", "status", "visibility")),
    "settlement": InspectionSchema("settlement", "Settlement", ("overview", "resources", "causes")),
    "faction": InspectionSchema("faction", "Faction", ("overview", "organization", "visibility")),
    "polity": InspectionSchema("polity", "Polity", ("overview", "legitimacy", "causes")),
    "war": InspectionSchema("war", "War", ("overview", "support", "causes")),
}
