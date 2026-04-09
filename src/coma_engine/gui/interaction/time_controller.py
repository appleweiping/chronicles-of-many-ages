from __future__ import annotations

from coma_engine.gui.session import GuiSession
from coma_engine.gui.types import WorldFrameProjection


class TimeController:
    def __init__(self, session: GuiSession):
        self.session = session

    def step_once(self) -> WorldFrameProjection:
        return self.session.step_once()

    def pause(self) -> None:
        self.session.set_running(False)

    def resume(self) -> None:
        self.session.set_running(True)
