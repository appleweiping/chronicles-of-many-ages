from __future__ import annotations

from coma_engine.gui.session import GuiSession


class SelectionController:
    def __init__(self, session: GuiSession):
        self.session = session

    def select(self, ref: str | None) -> None:
        self.session.select_ref(ref)
