from __future__ import annotations

from coma_engine.core.state import WorldState
from coma_engine.gui.types import InfoFlowProjection


def project_info_flows(world: WorldState, limit: int = 160) -> tuple[InfoFlowProjection, ...]:
    packet_deliveries: dict[str, list[str]] = world.history_index["packet_deliveries"]  # type: ignore[assignment]
    flows: list[InfoFlowProjection] = []
    for packet in sorted(world.info_packets, key=lambda item: (item.created_step, item.id), reverse=True)[:limit]:
        flows.append(
            InfoFlowProjection(
                packet_id=packet.id,
                content_domain=packet.content_domain,
                subject_ref=packet.subject_ref,
                location_ref=packet.location_ref,
                source_event_id=packet.source_event_id,
                strength=packet.strength,
                distortion=packet.distortion,
                visibility_scope=packet.visibility_scope,
                propagation_channels=tuple(packet.propagation_channels),
                delivered_to=tuple(packet_deliveries.get(packet.id, [])),
            )
        )
    return tuple(flows)
