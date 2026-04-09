from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from coma_engine.gui.types import WorldFrameProjection


@dataclass(slots=True)
class ProjectionStore:
    current: WorldFrameProjection | None = None
    previous: WorldFrameProjection | None = None
    recent: deque[WorldFrameProjection] = field(default_factory=lambda: deque(maxlen=6))
