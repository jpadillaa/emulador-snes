"""Sistema visual centralizado: tokens de color, tipografía, espaciado y radio.

Define las dos variantes de tema (claro y oscuro) descritas en la
especificación y genera la hoja de estilos (QSS) de la aplicación a partir
de los tokens. Todo el color de la interfaz se deriva de aquí; ningún widget
debe codificar colores propios.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# --- Espaciado (rejilla base 8 px) -----------------------------------------
MARGIN_WINDOW = 20      # margenes del cuerpo (DESIGN.md: margin-window)
SECTION_GAP = 32        # separacion entre regiones mayores del panel
STACK_GAP = 16          # separacion entre escenario y barra de acciones
GUTTER_SIDEBAR = 12     # separacion interna del panel
PADDING_CONTROL = 8     # padding interno de controles

# --- Radios -----------------------------------------------------------------
RADIUS_SURFACE = 12     # escenario y panel de control
RADIUS_CONTROL = 6      # botones e inputs

# --- Dimensiones de referencia ---------------------------------------------
WINDOW_INITIAL = (1360, 860)
WINDOW_MINIMUM = (1024, 700)
PANEL_WIDTH = 320
ACTION_BAR_HEIGHT = 88
STAGE_PADDING = 16
STAGE_MIN_USABLE_WIDTH = 480
ASSIGN_BUTTON_MIN_WIDTH = 104


class ThemeName(str, Enum):
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True)
class Palette:
    """Roles cromaticos de un tema. Los nombres replican la especificacion."""
    bg: str               # fondo principal
    surface: str          # superficie de paneles
    stage_surface: str    # superficie del escenario
    elevated: str         # superficie elevada
    elevated_max: str     # superficie elevada maxima
    text_primary: str
    text_secondary: str
    border: str           # borde y outline
    border_subtle: str    # borde sutil / outline fuerte
    accent: str           # acento primario
    accent_strong: str    # acento saturado (hover/pressed de accion primaria)
    on_accent: str        # texto/icono sobre el acento primario
    connected: str        # estado conectado
    reconnecting: str     # estado reconectando
    error: str            # estado error
    control_fill: str     # relleno de control
    control_hover: str    # hover de control


LIGHT = Palette(
    bg="#F5F5F7",
    surface="#FFFFFF",
    stage_surface="#FAFAFA",
    elevated="#FFFFFF",
    elevated_max="#F0F0F2",
    text_primary="#1D1D1F",
    text_secondary="#6E6E73",
    border="#D2D2D7",
    border_subtle="#E5E5EA",
    accent="#007AFF",
    accent_strong="#0051D5",
    on_accent="#FFFFFF",
    connected="#34C759",
    reconnecting="#FF9F0A",
    error="#FF3B30",
    control_fill="#FFFFFF",
    control_hover="#F0F0F2",
)

# Tokens alineados con docs/stitch_super_native_snes/native_emulator_pro/DESIGN.md
DARK = Palette(
    bg="#121317",                  # background / surface
    surface="#1E1F23",             # surface-container
    stage_surface="#0D0E12",       # surface-container-lowest (el "escenario")
    elevated="#292A2E",            # surface-container-high
    elevated_max="#343539",        # surface-container-highest
    text_primary="#E3E2E7",        # on-surface
    text_secondary="#C1C6D7",      # on-surface-variant
    border="#414755",              # outline-variant (borde de paneles)
    border_subtle="#8B90A0",       # outline
    accent="#ADC6FF",              # primary
    accent_strong="#4B8EFF",       # primary-container
    on_accent="#002E69",           # on-primary
    connected="#34C759",
    reconnecting="#FFB454",
    error="#FFB4AB",               # error
    control_fill="#343539",        # surface-container-highest
    control_hover="#38393D",       # surface-bright
)


def palette_for(name: ThemeName) -> Palette:
    return DARK if name == ThemeName.DARK else LIGHT


# --- Tipografia -------------------------------------------------------------
# (familia, tamano px, peso). La familia se resuelve por plataforma en runtime.
FONT_HEADLINE_LG = (24, 700)
FONT_HEADLINE_MD = (18, 600)
FONT_BODY_LG = (13, 400)
FONT_BODY_SM = (11, 400)
FONT_LABEL_MD = (12, 500)
FONT_LABEL_CAPS = (10, 700)


def system_font_family() -> str:
    import sys
    if sys.platform == "darwin":
        return ".AppleSystemUIFont"
    if sys.platform.startswith("win"):
        return "Segoe UI"
    return "Inter"


def mono_font_family() -> str:
    """Fuente monoespaciada disponible por plataforma (evita el alias generico
    'monospace', que Qt no resuelve y genera una advertencia)."""
    import sys
    if sys.platform == "darwin":
        return "Menlo"
    if sys.platform.startswith("win"):
        return "Consolas"
    return "DejaVu Sans Mono"


def build_stylesheet(name: ThemeName) -> str:
    """Genera el QSS completo de la aplicacion para el tema indicado."""
    p = palette_for(name)
    family = system_font_family()
    mono = mono_font_family()
    return f"""
    * {{
        font-family: "{family}";
        color: {p.text_primary};
    }}
    QMainWindow, QWidget#WidgetCentral {{
        background-color: {p.bg};
    }}

    /* --- Superficies con esquinas redondeadas --- */
    QFrame#EscenarioJuego {{
        background-color: {p.stage_surface};
        border: 1px solid {p.border};
        border-radius: {RADIUS_SURFACE}px;
    }}
    QFrame#BarraAcciones, QFrame#PanelControl {{
        background-color: {p.surface};
        border: 1px solid {p.border};
        border-radius: {RADIUS_SURFACE}px;
    }}

    /* --- Tipografia por rol --- */
    QLabel[role="headline-lg"] {{ font-size: 24px; font-weight: 700; }}
    QLabel[role="headline-md"] {{ font-size: 18px; font-weight: 600; }}
    QLabel[role="body-lg"]     {{ font-size: 13px; font-weight: 400; color: {p.text_primary}; }}
    QLabel[role="body-sm"]     {{ font-size: 11px; font-weight: 400; color: {p.text_secondary}; }}
    QLabel[role="label-md"]    {{ font-size: 12px; font-weight: 500; color: {p.text_secondary}; }}
    QLabel[role="label-caps"]  {{
        font-size: 10px; font-weight: 700; color: {p.text_secondary};
        letter-spacing: 1px;
    }}
    QLabel[role="card-title"]  {{ font-size: 18px; font-weight: 700; letter-spacing: 1px; }}
    QLabel[role="card-desc"]   {{ font-size: 13px; color: {p.text_secondary}; }}

    /* --- Botones de la barra de acciones --- */
    QToolButton#AccionBarra {{
        background-color: transparent;
        border: none;
        border-radius: {RADIUS_CONTROL}px;
        padding: 6px 12px;
        color: {p.text_primary};
        font-size: 12px;
        font-weight: 600;
    }}
    QToolButton#AccionBarra:hover {{ background-color: {p.control_hover}; }}
    QToolButton#AccionBarra:pressed {{ background-color: {p.elevated_max}; }}
    QToolButton#AccionBarra:disabled {{ color: {p.text_secondary}; }}

    /* --- Separador vertical --- */
    QFrame#Separador {{ color: {p.border}; background-color: {p.border}; }}

    /* --- Control segmentado --- */
    QFrame#ControlSegmentado {{
        background-color: {p.elevated_max};
        border-radius: {RADIUS_CONTROL}px;
        border: 1px solid {p.border_subtle};
    }}
    QPushButton#SegmentoPestana {{
        background-color: transparent;
        border: none;
        border-radius: {RADIUS_CONTROL - 1}px;
        padding: 6px 10px;
        font-size: 12px;
        font-weight: 600;
        color: {p.text_secondary};
    }}
    QPushButton#SegmentoPestana:checked {{
        background-color: {p.surface};
        border: 1px solid {p.border};
        color: {p.text_primary};
    }}

    /* --- Botones genericos --- */
    QPushButton {{
        background-color: {p.control_fill};
        border: 1px solid {p.border};
        border-radius: {RADIUS_CONTROL}px;
        padding: 7px 14px;
        font-size: 13px;
        color: {p.text_primary};
    }}
    QPushButton:hover {{ background-color: {p.control_hover}; }}
    QPushButton:pressed {{ background-color: {p.elevated_max}; }}
    QPushButton#Primario {{
        background-color: {p.accent};
        border: none;
        color: {p.on_accent};
        font-weight: 600;
    }}
    QPushButton#Primario:hover {{ background-color: {p.accent_strong}; color: #FFFFFF; }}
    QPushButton#Primario:pressed {{ background-color: {p.accent_strong}; color: #FFFFFF; }}
    /* Etiqueta del fisico asignado: forma de pildora (DESIGN.md: Mapping Slots) */
    QPushButton#BotonAsignacion {{
        min-width: {ASSIGN_BUTTON_MIN_WIDTH}px;
        border-radius: 14px;
        font-family: "{mono}";
        font-size: 12px;
    }}
    QPushButton#BotonAsignacion[listening="true"] {{
        border: 1px solid {p.accent};
        color: {p.accent};
    }}

    /* --- ComboBox --- */
    QComboBox {{
        background-color: {p.control_fill};
        border: 1px solid {p.border};
        border-radius: {RADIUS_CONTROL}px;
        padding: 6px 10px;
        font-size: 13px;
        min-height: 18px;
    }}
    QComboBox:hover {{ background-color: {p.control_hover}; }}
    QComboBox QAbstractItemView {{
        background-color: {p.surface};
        border: 1px solid {p.border};
        border-radius: {RADIUS_CONTROL}px;
        padding: 4px;
        outline: none;
        selection-background-color: {p.accent};
        selection-color: {p.on_accent};
    }}
    QToolButton#BotonRefrescar {{
        background-color: {p.control_fill};
        border: 1px solid {p.border};
        border-radius: {RADIUS_CONTROL}px;
        padding: 6px;
    }}
    QToolButton#BotonRefrescar:hover {{ background-color: {p.control_hover}; }}

    /* --- Scroll area --- */
    QScrollArea {{ border: none; background: transparent; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {p.border}; border-radius: 5px; min-height: 30px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

    /* --- Tarjetas de estado --- */
    QFrame#TarjetaEstado {{
        background-color: transparent;
    }}
    QLabel#IconoTarjeta {{ font-size: 56px; }}
    QFrame#Pildora {{
        background-color: {p.elevated_max};
        border-radius: 11px;
        padding: 2px 10px;
    }}
    QLabel[role="pildora"] {{ font-size: 11px; font-weight: 600; color: {p.text_secondary}; }}

    /* --- Filas de mapeo --- */
    QFrame#FilaMapeo {{
        background-color: {p.elevated};
        border: 1px solid {p.border_subtle};
        border-radius: {RADIUS_CONTROL}px;
    }}
    QLabel#IconoEntrada {{ font-size: 16px; }}

    /* --- Ilustracion / contenedores redondeados --- */
    QFrame#ContenedorIlustracion {{
        background-color: {p.elevated};
        border: 1px solid {p.border_subtle};
        border-radius: {RADIUS_SURFACE}px;
    }}
    """
