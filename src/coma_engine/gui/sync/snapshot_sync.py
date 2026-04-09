from __future__ import annotations

from coma_engine.core.state import WorldState
from coma_engine.gui.sync.projection_store import ProjectionStore
from coma_engine.gui.sync.world_projector import WorldProjector
from coma_engine.gui.types import WorldFrameProjection


class SnapshotSynchronizer:
    def __init__(self, store: ProjectionStore, projector: WorldProjector | None = None):
        self.store = store
        self.projector = projector or WorldProjector()

    def sync(self, world: WorldState) -> WorldFrameProjection:
        frame = self.projector.project(world)
        self.store.current = frame
        return frame
