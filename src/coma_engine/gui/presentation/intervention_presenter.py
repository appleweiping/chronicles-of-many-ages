from __future__ import annotations

from coma_engine.gui.types import InterventionOptionProjection


def build_intervention_options(target_ref: str) -> tuple[InterventionOptionProjection, ...]:
    if target_ref.startswith("npc:"):
        return (
            InterventionOptionProjection(
                action_id="bless",
                label="Favor Leader",
                description="Channel a formal blessing toward this figure through the approved modifier path.",
                target_ref=target_ref,
                channel="modifier",
                enabled=True,
                impact_hint="Useful when a visible actor seems fragile, embattled, or politically important.",
                emphasis="support",
                preview_lines=(
                    "Targets the selected figure only.",
                    "Resolves through the formal modifier channel next step.",
                    "Exact downstream outcome remains uncertain.",
                ),
            ),
        )
    if target_ref.startswith(("tile:", "settlement:")):
        return (
            InterventionOptionProjection(
                action_id="resource",
                label="Bless Harvest",
                description="Push relief and abundance toward this place through the existing resource-modifier path.",
                target_ref=target_ref,
                channel="modifier",
                enabled=True,
                impact_hint="Best for instability, shortages, and visible settlement pressure.",
                emphasis="stabilize",
                preview_lines=(
                    "Likely to ease local strain over the next few steps.",
                    "Acts through the formal modifier channel.",
                    "Most useful where food pressure or unrest is already visible.",
                ),
            ),
            InterventionOptionProjection(
                action_id="rumor",
                label="Seed Rumor",
                description="Inject a new formal information packet into this region and let propagation carry it.",
                target_ref=target_ref,
                channel="info_packet",
                enabled=target_ref.startswith("tile:"),
                impact_hint="Useful when you want attention, uncertainty, or belief pressure to spread.",
                emphasis="info",
                preview_lines=(
                    "Likely to increase rumor pressure in this region.",
                    "Depends on visibility, local spread, and existing information flow.",
                    "Will not predict exact downstream interpretation.",
                ),
            ),
            InterventionOptionProjection(
                action_id="miracle",
                label="Spread Omen",
                description="Create a dramatic formal event in the selected region without bypassing the event system.",
                target_ref=target_ref,
                channel="event",
                enabled=target_ref.startswith("tile:"),
                impact_hint="High-visibility move for moments that should feel decisive or unforgettable.",
                emphasis="mystic",
                preview_lines=(
                    "Will enter through the event channel rather than direct state editing.",
                    "Likely to create strong visible interpretation if the region can see it.",
                    "Exact follow-on effects remain formal-system dependent.",
                ),
            ),
        )
    return ()
