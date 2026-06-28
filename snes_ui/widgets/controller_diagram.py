"""Diagrama de mando SNES pintado.

Dibuja una representacion estilizada de un control SNES y resalta en tiempo
real las entradas presionadas. Se usa tanto como ilustracion estatica en la
seccion de asignacion como en la vista de visualizacion del control en vivo.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..theme import Palette

# Colores icónicos de los botones del Super Famicom (A rojo, B amarillo,
# X azul, Y verde). Iguales en ambos temas; el tono en reposo se atenúa
# mezclándolo con el color del cuerpo.
_FACE_COLORS = {
    "a": "#E04B3C",   # rojo
    "b": "#F0B429",   # amarillo
    "x": "#3B7DDD",   # azul
    "y": "#34A56F",   # verde
}


class ControllerDiagram(QWidget):
    def __init__(self, palette: Palette, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._p = palette
        self._pressed: set[str] = set()
        self.setMinimumHeight(120)

    def set_palette(self, palette: Palette) -> None:
        self._p = palette
        self.update()

    def set_pressed(self, pressed: set[str]) -> None:
        if pressed != self._pressed:
            self._pressed = set(pressed)
            self.update()

    def _color(self, key: str, base: str) -> QColor:
        return QColor(self._p.accent) if key in self._pressed else QColor(base)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Lienzo con relacion 2:1 centrado; toda la geometria se calcula en
        # pixeles a partir de la unidad u = altura del lienzo / 100.
        w, h = self.width(), self.height()
        cw = min(w, h * 2.0)
        ch = cw / 2.0
        ox = (w - cw) / 2.0
        oy = (h - ch) / 2.0
        u = ch / 100.0  # unidad de trabajo

        def px(nx: float) -> float:
            return ox + nx * cw

        def py(ny: float) -> float:
            return oy + ny * ch

        outline = QColor(self._p.border)
        recessed = QColor(self._p.surface)   # color de los controles "hundidos"
        is_dark = QColor(self._p.bg).lightness() < 128
        # Realce de luz superior (rim) y sombra de pie de cada control.
        rim = QColor(255, 255, 255, 28 if is_dark else 150)

        # --- Hombros L / R (bumpers metidos bajo el borde superior) ---
        shoulder_w, shoulder_h = 26 * u, 18 * u
        for key, cx_n in (("l", 0.215), ("r", 0.785)):
            rect = QRectF(px(cx_n) - shoulder_w / 2, py(0.045),
                          shoulder_w, shoulder_h)
            p.setPen(QPen(outline, max(1.0, u)))
            p.setBrush(self._color(key, self._p.elevated))
            p.drawRoundedRect(rect, 6 * u, 6 * u)
            self._centered_text(p, rect, key.upper(), 10 * u,
                                self._on(key), top=True)

        # --- Cuerpo del mando ---
        body = QRectF(px(0.04), py(0.20), cw * 0.92, ch * 0.60)
        radius = 20 * u
        p.setPen(QPen(outline, max(1.0, 1.4 * u)))
        p.setBrush(QColor(self._p.elevated_max))
        p.drawRoundedRect(body, radius, radius)
        # Rim de luz sutil en el borde interior (da volumen tipo macOS).
        inset = 1.6 * u
        p.setPen(QPen(rim, max(1.0, u)))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(body.adjusted(inset, inset, -inset, -inset),
                          radius - inset, radius - inset)

        # --- D-Pad (cruz hundida con pivote central) a la izquierda ---
        dpx, dpy = px(0.205), py(0.49)
        th = 14 * u           # grosor del brazo
        al = 20 * u           # longitud del brazo desde el centro
        r = 3.5 * u
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(recessed)
        vbar = QRectF(dpx - th / 2, dpy - al, th, 2 * al)
        hbar = QRectF(dpx - al, dpy - th / 2, 2 * al, th)
        p.drawRoundedRect(vbar, r, r)
        p.drawRoundedRect(hbar, r, r)
        # brazos presionados (resaltado)
        arms = {
            "up": QRectF(dpx - th / 2, dpy - al, th, al),
            "down": QRectF(dpx - th / 2, dpy, th, al),
            "left": QRectF(dpx - al, dpy - th / 2, al, th),
            "right": QRectF(dpx, dpy - th / 2, al, th),
        }
        for key, rect in arms.items():
            if key in self._pressed:
                p.setBrush(QColor(self._p.accent))
                p.drawRoundedRect(rect, r, r)
        # pivote central
        pivot = 4.5 * u
        p.setBrush(QColor(self._p.elevated_max))
        p.drawEllipse(QPointF(dpx, dpy), pivot, pivot)

        # --- Select / Start (centro): dos cápsulas paralelas, a la misma altura
        # e inclinadas hacia arriba-derecha (~30°), como en el mando real. Cada
        # una rota sobre su propio centro para que no queden escalonadas. ---
        pill_w, pill_h = 20 * u, 8 * u
        angle = -30
        cy = py(0.55)
        for key, cx in (("select", px(0.44)), ("start", px(0.565))):
            p.save()
            p.translate(cx, cy)
            p.rotate(angle)
            rect = QRectF(-pill_w / 2, -pill_h / 2, pill_w, pill_h)
            p.setPen(QPen(outline, max(1.0, u)))
            p.setBrush(self._color(key, recessed))
            p.drawRoundedRect(rect, pill_h / 2, pill_h / 2)
            p.restore()
        p.setPen(Qt.PenStyle.NoPen)
        self._label(p, px(0.435), py(0.75), "SELECT", 6.5 * u, self._p.text_secondary)
        self._label(p, px(0.57), py(0.75), "START", 6.5 * u, self._p.text_secondary)

        # --- Botones de accion (diamante Y/X/B/A) a la derecha ---
        fbx, fby = px(0.80), py(0.49)
        spread, br = 17 * u, 10.5 * u
        # Disposicion SNES: X arriba, B abajo, Y izquierda, A derecha.
        buttons = [
            ("x", QPointF(fbx, fby - spread)),
            ("b", QPointF(fbx, fby + spread)),
            ("y", QPointF(fbx - spread, fby)),
            ("a", QPointF(fbx + spread, fby)),
        ]
        body_c = QColor(self._p.elevated_max)
        for key, c in buttons:
            rect = QRectF(c.x() - br, c.y() - br, 2 * br, 2 * br)
            vivid = QColor(_FACE_COLORS[key])
            pressed = key in self._pressed
            # En reposo: tinte suave del color sobre el cuerpo; presionado: a
            # todo color (el botón "se enciende").
            fill = vivid if pressed else self._mix(vivid, body_c, 0.74)
            p.setPen(QPen(outline, max(1.0, u)))
            p.setBrush(fill)
            p.drawEllipse(rect)
            if pressed:
                letter = "#1D1D1F" if fill.lightness() > 150 else self._p.on_accent
            else:
                letter = self._p.text_primary
            self._centered_text(p, rect, key.upper(), 12 * u, letter)
        p.end()

    @staticmethod
    def _mix(a: QColor, b: QColor, t: float) -> QColor:
        """Mezcla lineal de a→b (t=0 → a, t=1 → b)."""
        return QColor(
            round(a.red() * (1 - t) + b.red() * t),
            round(a.green() * (1 - t) + b.green() * t),
            round(a.blue() * (1 - t) + b.blue() * t),
        )

    def _on(self, key: str) -> str:
        """Color del texto/etiqueta de un control segun este presionado o no."""
        return self._p.on_accent if key in self._pressed else self._p.text_primary

    def _label(self, p: QPainter, cx: float, cy: float, text: str, size: float,
               color: str) -> None:
        font = QFont()
        font.setPixelSize(max(6, int(size)))
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 104)
        p.setFont(font)
        p.setPen(QColor(color))
        rect = QRectF(cx - 60, cy - 12, 120, 24)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        p.setPen(Qt.PenStyle.NoPen)

    def _centered_text(self, p: QPainter, rect: QRectF, text: str, size: float,
                       color: str, top: bool = False) -> None:
        font = QFont()
        font.setPixelSize(max(7, int(size)))
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(color))
        align = Qt.AlignmentFlag.AlignHCenter | (
            Qt.AlignmentFlag.AlignTop if top else Qt.AlignmentFlag.AlignVCenter)
        p.drawText(rect, align, text)
        p.setPen(Qt.PenStyle.NoPen)
