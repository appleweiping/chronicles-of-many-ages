from __future__ import annotations

from coma_engine.gui.session import GuiSession
from coma_engine.player.interventions import (
    queue_information_intervention,
    queue_miracle_intervention,
    queue_npc_modifier_intervention,
    queue_resource_modifier_intervention,
)


class InterventionController:
    def __init__(self, session: GuiSession):
        self.session = session

    def bless_npc(self, npc_id: str) -> None:
        queue_npc_modifier_intervention(
            self.session.world,
            npc_id,
            modifier_type="player_blessing",
            domain="yield.food",
            magnitude=1.0,
            duration=3,
        )

    def resource_surge(self, target_ref: str) -> None:
        queue_resource_modifier_intervention(
            self.session.world,
            target_ref,
            modifier_type="abundance",
            domain="yield.food",
            magnitude=1.5,
            duration=3,
        )

    def spread_rumor(self, tile_ref: str) -> None:
        queue_information_intervention(
            self.session.world,
            content_domain="belief",
            subject_ref=None,
            location_ref=tile_ref,
            strength=25.0,
        )

    def invoke_miracle(self, tile_ref: str) -> None:
        queue_miracle_intervention(
            self.session.world,
            event_type="PLAYER_MIRACLE",
            location_ref=tile_ref,
            participant_ids=[],
        )
