from __future__ import annotations

from coma_engine.core.state import WorldState
from coma_engine.core.transfers import reconcile_references, validate_reference_consistency
from coma_engine.simulation.phases import (
    run_decision_phase,
    run_declaration_phase,
    run_environment_phase,
    run_event_phase,
    run_information_phase,
    run_need_update_phase,
    run_political_phase,
    run_resolution_phase,
    run_resource_phase,
)


PHASE_DISPATCH = {
    "EnvironmentPhase": run_environment_phase,
    "ResourcePhase": run_resource_phase,
    "NeedUpdatePhase": run_need_update_phase,
    "InformationPhase": run_information_phase,
    "DecisionPhase": run_decision_phase,
    "DeclarationPhase": run_declaration_phase,
    "ResolutionPhase": run_resolution_phase,
    "PoliticalPhase": run_political_phase,
    "EventPhase": run_event_phase,
}


class SimulationEngine:
    def __init__(self, world: WorldState):
        self.world = world

    def step(self) -> WorldState:
        for phase_name in self.world.config.design_constants.phase_order:
            snapshot = self.world.clone_for_phase()
            self.world.store_phase_snapshot(phase_name, snapshot)
            working = self.world.clone_for_phase()
            working.phase_snapshot_buffer = dict(self.world.phase_snapshot_buffer)
            PHASE_DISPATCH[phase_name](snapshot, working)
            reconcile_references(working)
            for error in validate_reference_consistency(working):
                working.log_error(f"{phase_name}:{error}")
            self.world.replace_with(working)
        self.world.current_step += 1
        return self.world
