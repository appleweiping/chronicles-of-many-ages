from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from coma_engine.core.state import WorldState
from coma_engine.gui.sync.projection_store import ProjectionStore
from coma_engine.gui.sync.snapshot_sync import SnapshotSynchronizer
from coma_engine.gui.types import GuiViewState, WorldFrameProjection
from coma_engine.simulation.engine import SimulationEngine


ProjectionListener = Callable[[WorldFrameProjection], None]


@dataclass(slots=True)
class GuiSession:
    world: WorldState
    engine: SimulationEngine = field(init=False)
    projections: ProjectionStore = field(init=False)
    synchronizer: SnapshotSynchronizer = field(init=False)
    view_state: GuiViewState = field(default_factory=GuiViewState)
    _listeners: list[ProjectionListener] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.engine = SimulationEngine(self.world)
        self.projections = ProjectionStore()
        self.synchronizer = SnapshotSynchronizer(self.projections)
        self.sync_now()

    def sync_now(self) -> WorldFrameProjection:
        frame = self.synchronizer.sync(self.world)
        for listener in list(self._listeners):
            listener(frame)
        return frame

    def subscribe(self, listener: ProjectionListener) -> None:
        self._listeners.append(listener)

    def unsubscribe(self, listener: ProjectionListener) -> None:
        self._listeners = [item for item in self._listeners if item is not listener]

    def step_once(self) -> WorldFrameProjection:
        self.engine.step()
        return self.sync_now()

    def set_running(self, running: bool) -> None:
        self.view_state.running = running

    def set_debug_mode(self, enabled: bool) -> None:
        self.view_state.debug_mode = enabled

    def select_ref(self, ref: str | None) -> None:
        self.view_state.selected_ref = ref

    @property
    def current_frame(self) -> WorldFrameProjection | None:
        return self.projections.current
