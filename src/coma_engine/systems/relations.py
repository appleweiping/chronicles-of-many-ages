from __future__ import annotations

from coma_engine.core.state import WorldState
from coma_engine.models.entities import NPC, RelationEntry


def ensure_relation_entry(world: WorldState, npc_id: str, other_id: str) -> RelationEntry:
    npc = world.npcs[npc_id]
    if other_id not in npc.relationships:
        npc.relationships[other_id] = RelationEntry()
    return npc.relationships[other_id]


def apply_relation_template(entry: RelationEntry, template_values: dict[str, float], scale: float = 1.0) -> RelationEntry:
    for axis, delta in template_values.items():
        setattr(entry, axis, max(0.0, min(100.0, getattr(entry, axis) + delta * scale)))
    return entry


def apply_relation_template_between(
    world: WorldState,
    source_id: str,
    target_id: str,
    template_name: str,
    *,
    scale: float = 1.0,
    reciprocal: str | None = None,
) -> None:
    templates = world.config.balance_parameters.relation_templates
    template_values = templates.get(template_name)
    if template_values is None or source_id not in world.npcs or target_id not in world.npcs:
        return
    source_entry = ensure_relation_entry(world, source_id, target_id)
    apply_relation_template(source_entry, template_values, scale)
    relation_log: list[dict[str, object]] = world.history_index["relation_log"]  # type: ignore[assignment]
    relation_log.append(
        {
            "step": world.current_step,
            "source_id": source_id,
            "target_id": target_id,
            "template": template_name,
            "scale": round(scale, 2),
        }
    )
    if reciprocal:
        reciprocal_values = templates.get(reciprocal)
        if reciprocal_values is not None:
            reciprocal_entry = ensure_relation_entry(world, target_id, source_id)
            apply_relation_template(reciprocal_entry, reciprocal_values, scale)
            relation_log.append(
                {
                    "step": world.current_step,
                    "source_id": target_id,
                    "target_id": source_id,
                    "template": reciprocal,
                    "scale": round(scale, 2),
                }
            )


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
