from __future__ import annotations

from coma_engine.core.state import WorldState


def queue_npc_modifier_intervention(
    world: WorldState,
    npc_id: str,
    *,
    modifier_type: str,
    domain: str,
    magnitude: float,
    duration: int,
) -> None:
    world.delayed_effect_queue.append(
        {
            "activation_step": world.current_step,
            "channel": "modifier",
            "target_ref": npc_id,
            "modifier_type": modifier_type,
            "domain": domain,
            "magnitude": magnitude,
            "duration": duration,
            "source_ref": "player",
        }
    )
    world.player_state.intervention_history.append(f"modifier:{npc_id}:{modifier_type}")


def queue_resource_modifier_intervention(
    world: WorldState,
    target_ref: str,
    *,
    modifier_type: str,
    domain: str,
    magnitude: float,
    duration: int,
) -> None:
    if not (target_ref.startswith("tile:") or target_ref.startswith("settlement:")):
        raise ValueError("resource interventions may only target tile or settlement references")
    world.delayed_effect_queue.append(
        {
            "activation_step": world.current_step,
            "channel": "modifier",
            "target_ref": target_ref,
            "modifier_type": modifier_type,
            "domain": domain,
            "magnitude": magnitude,
            "duration": duration,
            "source_ref": "player",
        }
    )
    world.player_state.intervention_history.append(f"resource_modifier:{target_ref}:{modifier_type}")


def queue_information_intervention(
    world: WorldState,
    *,
    content_domain: str,
    subject_ref: str | None,
    location_ref: str | None,
    strength: float,
) -> None:
    world.delayed_effect_queue.append(
        {
            "activation_step": world.current_step,
            "channel": "info_packet",
            "content_domain": content_domain,
            "subject_ref": subject_ref,
            "location_ref": location_ref,
            "strength": strength,
            "source_ref": "player",
        }
    )
    world.player_state.intervention_history.append(f"info:{content_domain}:{subject_ref}")


def queue_miracle_intervention(
    world: WorldState,
    *,
    event_type: str,
    location_ref: str,
    participant_ids: list[str],
) -> None:
    world.delayed_effect_queue.append(
        {
            "activation_step": world.current_step,
            "channel": "event",
            "event_type": event_type,
            "location_ref": location_ref,
            "participant_ids": participant_ids,
            "source_ref": "player",
        }
    )
    world.player_state.intervention_history.append(f"event:{event_type}:{location_ref}")
