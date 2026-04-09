from __future__ import annotations

from coma_engine.gui.session import GuiSession


class CameraController:
    def __init__(self, session: GuiSession):
        self.session = session

    def zoom_by(self, delta: float) -> None:
        self.session.view_state.zoom_level = max(0.25, min(4.0, self.session.view_state.zoom_level + delta))

    def pan_by(self, dx: float, dy: float) -> None:
        self.session.view_state.pan_x += dx
        self.session.view_state.pan_y += dy
