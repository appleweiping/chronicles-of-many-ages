from __future__ import annotations

from coma_engine.gui.session import GuiSession


class OverlayController:
    def __init__(self, session: GuiSession):
        self.session = session

    def set_enabled(self, overlay_name: str, enabled: bool) -> None:
        if enabled:
            self.session.view_state.active_overlays.add(overlay_name)
        else:
            self.session.view_state.active_overlays.discard(overlay_name)

    def is_enabled(self, overlay_name: str) -> bool:
        return overlay_name in self.session.view_state.active_overlays

    def set_map_mode(self, map_mode: str) -> None:
        self.session.view_state.current_map_mode = map_mode  # type: ignore[assignment]
