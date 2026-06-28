"""Iconografía de línea: registro completo, render no vacío y coherencia.

Verifica que (1) cada icono del registro renderiza un pixmap no nulo y que
(2) todos los nombres de icono referenciados por los widgets existen en el
registro, de modo que un nombre mal escrito rompa el test y no la UI.
"""
from __future__ import annotations

from snes_ui.widgets import icons
from snes_ui.widgets.action_bar import ACTIONS


def test_all_registered_icons_render(qapp):
    for name in icons.icon_names():
        pm = icons.line_pixmap(name, 24, "#112233")
        assert not pm.isNull()
        assert pm.width() > 0 and pm.height() > 0


def test_action_bar_icons_exist_in_registry(qapp):
    registry = set(icons.icon_names())
    for spec in ACTIONS:
        assert spec.icon in registry, f"icono inexistente: {spec.icon}"


def test_state_card_and_refresh_icons_exist(qapp):
    registry = set(icons.icon_names())
    # Iconos usados por GameStage / StateCard y el botón de refrescar.
    for name in ("controller", "hourglass", "pause", "warning", "refresh"):
        assert name in registry


def test_tint_changes_pixels(qapp):
    """Dos colores distintos producen pixmaps distintos (el tinte se aplica)."""
    a = icons.line_pixmap("pause", 24, "#000000").toImage()
    b = icons.line_pixmap("pause", 24, "#FFFFFF").toImage()
    assert a != b
