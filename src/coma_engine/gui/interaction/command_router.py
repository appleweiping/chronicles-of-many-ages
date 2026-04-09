from __future__ import annotations

from coma_engine.gui.interaction.intervention_controller import InterventionController


class CommandRouter:
    def __init__(self, interventions: InterventionController):
        self.interventions = interventions

    def dispatch(self, action_id: str, target_ref: str) -> None:
        if action_id == "bless" and target_ref.startswith("npc:"):
            self.interventions.bless_npc(target_ref)
        elif action_id == "resource":
            self.interventions.resource_surge(target_ref)
        elif action_id == "rumor" and target_ref.startswith("tile:"):
            self.interventions.spread_rumor(target_ref)
        elif action_id == "miracle" and target_ref.startswith("tile:"):
            self.interventions.invoke_miracle(target_ref)
