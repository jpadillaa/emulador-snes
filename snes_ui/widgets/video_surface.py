"""Superficie de video.

Widget dedicado a presentar el fotograma renderizado por el nucleo. Aplica
los cuatro modos de escalado con letterboxing y respeta el devicePixelRatio
del monitor activo. No conoce la procedencia del fotograma: lo recibe como
QImage desde el adaptador del nucleo.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QWidget

from ..state import ScaleMode


class VideoSurface(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image: QImage | None = None
        self._mode = ScaleMode.FIT_WINDOW
        self.setMinimumSize(160, 120)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    def set_mode(self, mode: ScaleMode) -> None:
        self._mode = mode
        self.update()

    def set_image(self, image: QImage) -> None:
        self._image = image
        self.update()

    def clear(self) -> None:
        self._image = None
        self.update()

    def _target_rect(self, src_w: int, src_h: int) -> QRect:
        """Calcula el rectangulo de destino segun el modo de escalado."""
        w, h = self.width(), self.height()
        if self._mode == ScaleMode.STRETCH:
            return QRect(0, 0, w, h)

        if self._mode == ScaleMode.ORIGINAL:
            # Relacion de pixel 8:7 del hardware aplicada al ancho.
            aspect = (src_w * 8 / 7) / src_h
        else:
            aspect = 4 / 3  # ajuste a ventana / entero (4:3 de UI)

        if self._mode == ScaleMode.INTEGER:
            scale = max(1, min(w // src_w, h // src_h))
            tw, th = src_w * scale, src_h * scale
        else:
            # Maximizar manteniendo relacion de aspecto (letterboxing).
            if w / h > aspect:
                th = h
                tw = int(h * aspect)
            else:
                tw = w
                th = int(w / aspect)
        x = (w - tw) // 2
        y = (h - th) // 2
        return QRect(x, y, tw, th)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#000000"))  # barras de letterbox
        if self._image is None or self._image.isNull():
            painter.end()
            return
        rect = self._target_rect(self._image.width(), self._image.height())
        smooth = self._mode != ScaleMode.INTEGER
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, smooth)
        painter.drawImage(rect, self._image)
        painter.end()
