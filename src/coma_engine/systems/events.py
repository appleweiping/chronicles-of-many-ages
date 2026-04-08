from __future__ import annotations

from coma_engine.actions.models import ActionOutcome
from coma_engine.core.enums import HistoricalLayer
from coma_engine.core.state import WorldState
from coma_engine.models.entities import Event, MemoryEntry
from coma_engine.systems.propagation import emit_info_packet


EVENT_TYPE_MAP: dict[tuple[str, str], tuple[str, str, str]] = {
    ("FORAGE", "succeeded"): ("RESOURCE_GATHERED", "forage_success", HistoricalLayer.RAW_EVENT.value),
    ("MOVE", "succeeded"): ("TRAVEL_COMPLETED", "move_success", HistoricalLayer.RAW_EVENT.value),
    ("MOVE", "partial"): ("TRAVEL_UNDERWAY", "move_partial", HistoricalLayer.RAW_EVENT.value),
    ("SCOUT", "partial"): ("SCOUTING_UNDERWAY", "scout_partial", HistoricalLayer.RAW_EVENT.value),
    ("SCOUT", "succeeded"): ("SCOUTING_COMPLETED", "scout_success", HistoricalLayer.LOCAL_CHRONICLE.value),
    ("TRADE", "succeeded"): ("TRADE_COMPLETED", "trade_success", HistoricalLayer.LOCAL_CHRONICLE.value),
    ("MIGRATE", "succeeded"): ("MIGRATION_COMPLETED", "migrate_success", HistoricalLayer.LOCAL_CHRONICLE.value),
    ("FOUND_POLITY", "succeeded"): ("POLITY_FOUNDED", "polity_founded", HistoricalLayer.CIVILIZATION_NODE.value),
    ("FOUND_POLITY", "failed"): ("FAILED_FOUNDING", "polity_found_failed", HistoricalLayer.LOCAL_CHRONICLE.value),
    ("FOUND_POLITY", "interrupted"): ("FOUNDING_INTERRUPTED", "polity_found_interrupted", HistoricalLayer.LOCAL_CHRONICLE.value),
    ("FORMAL_TAX_ORDER", "succeeded"): ("TAX_ORDER_ISSUED", "tax_order_issued", HistoricalLayer.LOCAL_CHRONICLE.value),
    ("LEVY_RESOURCES", "succeeded"): ("LEVY_ORDER_ISSUED", "resource_levy_issued", HistoricalLayer.LOCAL_CHRONICLE.value),
    ("DECLARE_WAR", "succeeded"): ("WAR_DECLARED", "war_declared", HistoricalLayer.CIVILIZATION_NODE.value),
    ("MUSTER_FORCE", "succeeded"): ("FORCE_MUSTER_ORDERED", "muster_force_ordered", HistoricalLayer.LOCAL_CHRONICLE.value),
    ("MUSTER_FORCE", "partial"): ("FORCE_MUSTER_UNDERWAY", "muster_force_partial", HistoricalLayer.LOCAL_CHRONICLE.value),
}


def materialize_outcomes(world: WorldState) -> None:
    outcomes_by_step: dict[int, list[str]] = world.history_index["outcomes_by_step"]  # type: ignore[assignment]
    events_by_step: dict[int, list[str]] = world.history_index["events_by_step"]  # type: ignore[assignment]
    event_layers: dict[str, list[str]] = world.history_index["event_layers"]  # type: ignore[assignment]
    for outcome in world.outcome_records:
        mapped = EVENT_TYPE_MAP.get((outcome.action_type, outcome.result))
        if not mapped:
            continue
        event_type, summary_code, history_layer = mapped
        event_id = world.next_id("event")
        location_ref = _infer_location(world, outcome)
        event = Event(
            id=event_id,
            event_type=event_type,
            timestamp_step=world.current_step,
            location_tile_id=location_ref,
            region_ref=None,
            participant_ids=list(dict.fromkeys(outcome.participant_ids)),
            cause_refs=[outcome.action_id, *outcome.cause_refs],
            outcome_summary_code=summary_code,
            importance=_importance_for(event_type, outcome),
            visibility_scope="local" if history_layer != HistoricalLayer.CIVILIZATION_NODE.value else "broad",
            derived_memory_ids=[],
            derived_modifier_ids=list(outcome.generated_modifier_ids),
            derived_info_packet_ids=[],
        )
        world.events[event_id] = event
        events_by_step.setdefault(world.current_step, []).append(event_id)
        event_layers[history_layer].append(event_id)
        outcomes_by_step.setdefault(world.current_step, []).append(outcome.action_id)
        _derive_memories(world, event)
        _derive_packets(world, event)
    _materialize_command_execution(world)


def _importance_for(event_type: str, outcome: ActionOutcome) -> float:
    if event_type in {"POLITY_FOUNDED", "WAR_DECLARED"}:
        return 90.0
    if event_type in {"TAX_ORDER_ISSUED", "LEVY_ORDER_ISSUED", "FAILED_FOUNDING", "FOUNDING_INTERRUPTED"}:
        return 55.0
    return 35.0 + abs(sum(outcome.resource_delta.values()))


def _infer_location(world: WorldState, outcome: ActionOutcome) -> str | None:
    for ref in outcome.target_refs:
        if ref.startswith("tile:"):
            return ref
        if ref.startswith("settlement:"):
            settlement = world.settlements.get(ref)
            if settlement:
                return settlement.core_tile_id
    actor = world.npcs.get(outcome.actor_id)
    return actor.location_tile_id if actor else None


def _derive_memories(world: WorldState, event: Event) -> None:
    for npc_id in event.participant_ids:
        if npc_id not in world.npcs:
            continue
        memory_id = world.next_id("memory")
        world.memories[memory_id] = MemoryEntry(
            id=memory_id,
            npc_id=npc_id,
            source_event_id=event.id,
            impression_strength=min(100.0, event.importance),
            emotion_tag="salient",
            decay_rate=0.1,
            bias_conversion_rule="default",
            created_step=world.current_step,
            current_effect_weight=event.importance * 0.1,
            is_conversion_ready=event.importance >= 70.0,
        )
        world.npcs[npc_id].memory_ids.append(memory_id)
        event.derived_memory_ids.append(memory_id)


def _derive_packets(world: WorldState, event: Event) -> None:
    packet_id = emit_info_packet(
        world,
        source_event_id=event.id,
        origin_actor_id=event.participant_ids[0] if event.participant_ids else None,
        content_domain="belief" if event.event_type == "POLITY_FOUNDED" else "event",
        subject_ref=event.participant_ids[0] if event.participant_ids else None,
        location_ref=event.location_tile_id,
        strength=min(100.0, event.importance * 0.8),
        visibility_scope=event.visibility_scope,
        ttl=3,
        truth_alignment=1.0,
        propagation_channels=["spatial", "relationship"],
    )
    event.derived_info_packet_ids.append(packet_id)


def _materialize_command_execution(world: WorldState) -> None:
    command_execution_log: list[dict[str, object]] = world.history_index["command_execution_log"]  # type: ignore[assignment]
    events_by_step: dict[int, list[str]] = world.history_index["events_by_step"]  # type: ignore[assignment]
    event_layers: dict[str, list[str]] = world.history_index["event_layers"]  # type: ignore[assignment]
    for entry in command_execution_log:
        if entry.get("step") != world.current_step or entry.get("materialized"):
            continue
        outcome = str(entry["outcome"])
        if outcome == "executed":
            event_type = "COMMAND_EXECUTED"
            importance = 52.0
        elif outcome == "delayed_distorted":
            event_type = "COMMAND_DELAYED"
            importance = 46.0
        elif outcome == "delayed_no_executor":
            event_type = "COMMAND_STALLED"
            importance = 44.0
        else:
            event_type = "COMMAND_RESISTED"
            importance = 58.0
        settlement_id = str(entry["settlement_id"])
        settlement = world.entity_by_ref(settlement_id)
        event_id = world.next_id("event")
        event = Event(
            id=event_id,
            event_type=event_type,
            timestamp_step=world.current_step,
            location_tile_id=getattr(settlement, "core_tile_id", None),
            region_ref=None,
            participant_ids=[],
            cause_refs=[str(entry["packet_id"]), str(entry["command_subject"])],
            outcome_summary_code=outcome,
            importance=importance,
            visibility_scope="local",
            derived_memory_ids=[],
            derived_modifier_ids=[],
            derived_info_packet_ids=[],
        )
        world.events[event_id] = event
        events_by_step.setdefault(world.current_step, []).append(event_id)
        event_layers[HistoricalLayer.LOCAL_CHRONICLE.value].append(event_id)
        _derive_packets(world, event)
        entry["materialized"] = True
