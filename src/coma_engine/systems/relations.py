from __future__ import annotations

from coma_engine.core.state import WorldState
from coma_engine.models.entities import NPC, RelationEntry


def apply_relation_template(entry: RelationEntry, template_name: str) -> RelationEntry:
    if template_name == "aid":
        entry.debt += 12.0
        entry.trust += 10.0
        entry.affinity += 4.0
    elif template_name == "betrayal":
        entry.trust -= 20.0
        entry.grievance += 18.0
        entry.fear += 8.0
    elif template_name == "shared_work":
        entry.familiarity += 5.0
        entry.trust += 2.0
    elif template_name == "repression":
        entry.fear += 16.0
        entry.grievance += 14.0
    elif template_name == "good_governance":
        entry.trust += 6.0
        entry.affinity += 4.0
    elif template_name == "extractive_taxation":
        entry.grievance += 10.0
        entry.affinity -= 5.0
    return entry


def compute_group_salience(world: WorldState, npc: NPC) -> dict[str, float]:
    scores: dict[str, float] = {"family": 20.0, "settlement": 0.0, "faction": 0.0, "polity": 0.0}
    scores["family"] += npc.personality.get("familiality", 0.0) * 0.4
    scores["family"] += npc.needs.get("safety", 0.0) * 0.1
    if npc.settlement_id:
        scores["settlement"] = 25.0 + npc.office_rank * 2.0 + npc.needs.get("social", 0.0) * 0.1
    if npc.faction_id:
        scores["faction"] = 22.0 + npc.office_rank * 5.0 + npc.beliefs.get("legitimacy_form", 0.0) * 0.1
    if npc.polity_id:
        scores["polity"] = 18.0 + npc.office_rank * 6.0 + npc.beliefs.get("destiny", 0.0) * 0.1
    for relation in npc.relationships.values():
        scores["family"] += relation.familiarity * 0.02
        scores["settlement"] += relation.trust * 0.01
    return {key: world.clamp_metric(value) for key, value in scores.items()}
