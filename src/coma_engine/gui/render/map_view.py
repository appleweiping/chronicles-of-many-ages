from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QWheelEvent
from PySide6.QtWidgets import QGraphicsView

from coma_engine.gui.render.map_scene import MapScene
from coma_engine.gui.render.map_scene import TILE_SIZE


class MapView(QGraphicsView):
    def __init__(self, scene: MapScene):
        super().__init__(scene)
        self.setRenderHints(self.renderHints() | QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("background-color: #0f1720; border: 1px solid #243241;")

    def wheelEvent(self, event: QWheelEvent) -> None:  # type: ignore[override]
        zoom = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(zoom, zoom)

    def focus_on_tile(self, x: int, y: int, *, zoom_level: float | None = None) -> None:
        self.centerOn(x * TILE_SIZE + TILE_SIZE / 2, y * TILE_SIZE + TILE_SIZE / 2)
        if zoom_level is not None:
            self.resetTransform()
            self.scale(zoom_level, zoom_level)
