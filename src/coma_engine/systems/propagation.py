from __future__ import annotations

from coma_engine.core.state import WorldState
from coma_engine.models.entities import InfoPacket, NPC
from coma_engine.models.perception import (
    BeliefSignalPerception,
    OpportunityPerception,
    PowerMapPerception,
    RecentEventPerception,
    ResourceSignalPerception,
    ThreatPerception,
)
from coma_engine.systems.spatial import traversable_neighbors


def emit_info_packet(
    world: WorldState,
    *,
    source_event_id: str | None,
    origin_actor_id: str | None,
    content_domain: str,
    subject_ref: str | None,
    location_ref: str | None,
    strength: float,
    visibility_scope: str,
    ttl: int,
    truth_alignment: float,
    propagation_channels: list[str],
) -> str:
    packet_id = world.next_id("packet")
    world.info_packets.append(
        InfoPacket(
            id=packet_id,
            source_event_id=source_event_id,
            origin_actor_id=origin_actor_id,
            content_domain=content_domain,
            subject_ref=subject_ref,
            location_ref=location_ref,
            strength=strength,
            distortion=0.0,
            visibility_scope=visibility_scope,
            remaining_ttl=ttl,
            propagation_channels=propagation_channels,
            truth_alignment=truth_alignment,
            created_step=world.current_step,
        )
    )
    return packet_id


def emit_command_packet(
    world: WorldState,
    actor_id: str,
    settlement_id: str,
    summary_code: str,
) -> str:
    packet_id = emit_info_packet(
        world,
        source_event_id=None,
        origin_actor_id=actor_id,
        content_domain="command",
        subject_ref=settlement_id,
        location_ref=world.settlements[settlement_id].core_tile_id,
        strength=65.0,
        visibility_scope="organizational",
        ttl=world.config.balance_parameters.command_base_ttl,
        truth_alignment=1.0,
        propagation_channels=["organizational"],
    )
    command_log: list[str] = world.history_index["command_log"]  # type: ignore[assignment]
    command_log.append(f"{packet_id}:{summary_code}")
    return packet_id


def _append_capped(channel: list, entry: object, capacity: int) -> None:
    channel.append(entry)
    channel.sort(key=lambda item: getattr(item, "expires_step", 0), reverse=True)
    del channel[capacity:]


def _deliver_packet_to_npc(world: WorldState, npc: NPC, packet: InfoPacket) -> None:
    expires = world.current_step + world.config.balance_parameters.default_perception_ttl
    capacity = world.config.balance_parameters.perception_channel_capacity
    state = npc.perceived_state
    if packet.content_domain in {"war", "threat", "command"}:
        _append_capped(
            state.perceived_threats,
            ThreatPerception(
                subject_ref=packet.subject_ref or "unknown",
                location_ref=packet.location_ref,
                threat_strength=packet.strength,
                source_ref=packet.id,
                credibility=1.0 - packet.distortion,
                expires_step=expires,
            ),
            capacity,
        )
    elif packet.content_domain == "resource":
        _append_capped(
            state.perceived_resource_signals,
            ResourceSignalPerception(
                location_ref=packet.location_ref or npc.location_tile_id,
                resource_type="food",
                abundance_signal=packet.strength,
                source_ref=packet.id,
                credibility=1.0 - packet.distortion,
                expires_step=expires,
            ),
            capacity,
        )
    elif packet.content_domain == "belief":
        _append_capped(
            state.perceived_belief_signals,
            BeliefSignalPerception(
                belief_domain="miracle_credibility",
                signal_strength=packet.strength,
                source_ref=packet.id,
                credibility=1.0 - packet.distortion,
                expires_step=expires,
            ),
            capacity,
        )
    elif packet.content_domain == "opportunity":
        _append_capped(
            state.perceived_opportunities,
            OpportunityPerception(
                subject_ref=packet.subject_ref or "unknown",
                location_ref=packet.location_ref,
                opportunity_kind="generic",
                estimated_benefit=packet.strength,
                source_ref=packet.id,
                credibility=1.0 - packet.distortion,
                expires_step=expires,
            ),
            capacity,
        )
    else:
        _append_capped(
            state.perceived_recent_events,
            RecentEventPerception(
                event_id=packet.source_event_id or packet.id,
                summary_code=packet.content_domain,
                importance=packet.strength,
                source_ref=packet.id,
                credibility=1.0 - packet.distortion,
                expires_step=expires,
            ),
            capacity,
        )
        _append_capped(
            state.perceived_power_map,
            PowerMapPerception(
                subject_ref=packet.subject_ref or "unknown",
                power_score=packet.strength,
                rank_hint=1,
                source_ref=packet.id,
                credibility=1.0 - packet.distortion,
                expires_step=expires,
            ),
            capacity,
        )


def propagate_info_packets(world: WorldState) -> None:
    delivered_pairs: set[tuple[str, str]] = set()
    for packet in world.info_packets:
        if packet.remaining_ttl <= 0 or packet.propagated_this_step:
            continue
        recipients: set[str] = set()
        if "spatial" in packet.propagation_channels and packet.location_ref:
            tile = world.tiles.get(packet.location_ref)
            if tile:
                recipients.update(tile.resident_npc_ids)
                for adjacent_id in traversable_neighbors(world, tile.id):
                    recipients.update(world.tiles[adjacent_id].resident_npc_ids)
        if "relationship" in packet.propagation_channels and packet.origin_actor_id in world.npcs:
            actor = world.npcs[packet.origin_actor_id]
            for target_id, relation in actor.relationships.items():
                if relation.familiarity + relation.trust > 20.0:
                    recipients.add(target_id)
        if "organizational" in packet.propagation_channels and packet.origin_actor_id in world.npcs:
            actor = world.npcs[packet.origin_actor_id]
            recipients.update(
                [
                    npc.id
                    for npc in world.npcs.values()
                    if npc.settlement_id == actor.settlement_id
                    or npc.faction_id == actor.faction_id
                    or npc.polity_id == actor.polity_id
                ]
            )
        for recipient_id in recipients:
            if recipient_id not in world.npcs:
                continue
            pair = (packet.id, recipient_id)
            if pair in delivered_pairs:
                continue
            delivered_pairs.add(pair)
            npc = world.npcs[recipient_id]
            if npc.alive:
                _deliver_packet_to_npc(world, npc, packet)
        packet.remaining_ttl -= 1
        packet.propagated_this_step = True
