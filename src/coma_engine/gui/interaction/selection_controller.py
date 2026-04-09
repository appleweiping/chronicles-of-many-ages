from __future__ import annotations

from coma_engine.gui.session import GuiSession


class SelectionController:
    def __init__(self, session: GuiSession):
        self.session = session

    def select(self, ref: str | None) -> None:
        self.session.select_ref(ref)
        if ref is not None:
            history = self.session.view_state.selection_history
            if not history or history[-1] != ref:
                history.append(ref)
            if len(history) > 12:
                del history[:-12]
