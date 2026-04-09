from __future__ import annotations

from dataclasses import dataclass

from coma_engine.gui.types import WorldFrameProjection


@dataclass(slots=True)
class ProjectionStore:
    current: WorldFrameProjection | None = None
