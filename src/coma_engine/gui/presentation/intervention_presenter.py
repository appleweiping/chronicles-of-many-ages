from __future__ import annotations

from coma_engine.gui.types import InterventionOptionProjection


def build_intervention_options(target_ref: str) -> tuple[InterventionOptionProjection, ...]:
    if target_ref.startswith("npc:"):
        return (
            InterventionOptionProjection(
                action_id="bless",
                label="Bless NPC",
                description="Queue a formal modifier intervention for this NPC.",
                target_ref=target_ref,
                channel="modifier",
                enabled=True,
            ),
        )
    if target_ref.startswith(("tile:", "settlement:")):
        return (
            InterventionOptionProjection(
                action_id="resource",
                label="Resource Surge",
                description="Queue a formal resource modifier intervention.",
                target_ref=target_ref,
                channel="modifier",
                enabled=True,
            ),
            InterventionOptionProjection(
                action_id="rumor",
                label="Spread Rumor",
                description="Queue a formal information intervention.",
                target_ref=target_ref,
                channel="info_packet",
                enabled=target_ref.startswith("tile:"),
            ),
            InterventionOptionProjection(
                action_id="miracle",
                label="Invoke Miracle",
                description="Queue a formal event intervention.",
                target_ref=target_ref,
                channel="event",
                enabled=target_ref.startswith("tile:"),
            ),
        )
    return ()
