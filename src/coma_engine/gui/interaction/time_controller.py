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
        self.session.view_state.speed_mode = "paused"

    def resume(self) -> None:
        self.session.set_running(True)
        self.session.view_state.speed_mode = "normal"

    def burst(self) -> None:
        self.session.set_running(True)
        self.session.view_state.speed_mode = "burst"
