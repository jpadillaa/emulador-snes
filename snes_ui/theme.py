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
# Radios mayores y continuos al estilo de macOS Tahoe (squircle).
RADIUS_SURFACE = 16     # escenario y panel de control
RADIUS_CONTROL = 8      # botones e inputs
RADIUS_GROUP = 12       # contenedor de lista "inset grouped"
RADIUS_CHIP = 980       # cápsula de atajo (forma de píldora completa)

# --- Dimensiones de referencia ---------------------------------------------
WINDOW_INITIAL = (1360, 860)
WINDOW_MINIMUM = (1024, 700)
PANEL_WIDTH = 320
ACTION_BAR_HEIGHT = 88
STAGE_PADDING = 16
STAGE_MIN_USABLE_WIDTH = 480
ASSIGN_BUTTON_MIN_WIDTH = 48


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
    disconnected: str     # estado desconectado
    error: str            # estado error
    control_fill: str     # relleno de control
    control_hover: str    # hover de control


# Tema claro alineado con los colores de sistema de macOS (Sonoma/Sequoia).
# Neutros con un tinte frío sutil y mayor separación de valor entre niveles
# (fondo más profundo → panel off-white → tarjetas blancas puras) para que las
# superficies "floten" y el conjunto no se vea plano.
LIGHT = Palette(
    bg="#E4E6EC",                  # fondo de ventana (gris frío, más profundo)
    surface="#F6F7FA",             # superficies de panel (off-white frío)
    stage_surface="#ECEEF3",       # escenario
    elevated="#FFFFFF",            # tarjetas / lista inset (blanco puro, resalta)
    elevated_max="#E9EBF1",        # cápsulas / superficie elevada máxima
    text_primary="#1D1D1F",
    text_secondary="#83838B",      # etiqueta secundaria macOS
    border="#D6D8DF",              # separador capilar (frío)
    border_subtle="#E4E6EC",       # separador aún más sutil
    accent="#007AFF",              # systemBlue
    accent_strong="#0060DF",
    on_accent="#FFFFFF",
    connected="#34C759",
    reconnecting="#FF9500",
    disconnected="#8E8E93",        # systemGray
    error="#FF3B30",
    control_fill="#FFFFFF",
    control_hover="#EDEFF4",
)

# Tema oscuro alineado con los colores de sistema de macOS Tahoe.
# Neutros sin tinte azulado, acento systemBlue vibrante, separadores capilares.
DARK = Palette(
    bg="#1C1C1E",                  # fondo de ventana
    surface="#2C2C2E",             # superficies de panel (material esmerilado)
    stage_surface="#0B0B0C",       # escenario (negro neutro, casi puro)
    elevated="#363638",            # tarjetas / lista inset
    elevated_max="#48484A",        # superficie elevada máxima / cápsulas
    text_primary="#F5F5F7",        # label primario
    text_secondary="#98989D",      # label secundario (gris neutro)
    border="#3A3A3C",              # separador capilar
    border_subtle="#2E2E30",       # separador aún más sutil
    accent="#0A84FF",              # systemBlue (oscuro)
    accent_strong="#409CFF",       # hover (más claro sobre fondo oscuro)
    on_accent="#FFFFFF",
    connected="#30D158",           # systemGreen (oscuro)
    reconnecting="#FF9F0A",        # systemOrange (oscuro)
    disconnected="#98989D",        # systemGray (oscuro)
    error="#FF453A",               # systemRed (oscuro)
    control_fill="#3A3A3C",        # relleno de control sobre el panel
    control_hover="#48484A",
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


def build_stylesheet(name: ThemeName) -> str:
    """Genera el QSS completo de la aplicacion para el tema indicado."""
    p = palette_for(name)
    family = system_font_family()
    # Realce capilar superior que simula el borde de luz de un material esmerilado
    # (vidrio) de macOS. Se aplica como segundo borde sutil sobre las superficies.
    glass_edge = "rgba(255, 255, 255, 0.10)" if name == ThemeName.DARK else "rgba(255, 255, 255, 0.70)"
    # Lavado rojo sutil para el hover/pressed de la acción destructiva (reset).
    is_dark = name == ThemeName.DARK
    error_tint = "rgba(255, 69, 58, 0.16)" if is_dark else "rgba(255, 59, 48, 0.10)"
    error_tint_strong = "rgba(255, 69, 58, 0.28)" if is_dark else "rgba(255, 59, 48, 0.18)"
    # Lavado azul sutil para el hover de controles reasignables.
    accent_tint = "rgba(10, 132, 255, 0.16)" if is_dark else "rgba(0, 122, 255, 0.09)"
    # Centro (más claro) del gradiente radial del escenario, para darle volumen
    # en vez de un color plano.
    stage_center = "#18181B" if is_dark else "#F5F6FA"
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
        background-color: qradialgradient(
            cx:0.5, cy:0.42, radius:0.9, fx:0.5, fy:0.42,
            stop:0 {stage_center}, stop:1 {p.stage_surface});
        border: 1px solid {p.border_subtle};
        border-radius: {RADIUS_SURFACE}px;
    }}
    /* Panel y barra como material esmerilado: superficie elevada + realce de luz. */
    QFrame#BarraAcciones, QFrame#PanelControl {{
        background-color: {p.surface};
        border: 1px solid {glass_edge};
        border-radius: {RADIUS_SURFACE}px;
    }}

    /* --- Tipografia por rol --- */
    QLabel[role="headline-lg"] {{ font-size: 24px; font-weight: 700; }}
    QLabel[role="headline-md"] {{ font-size: 18px; font-weight: 600; }}
    QLabel[role="body-lg"]     {{ font-size: 13px; font-weight: 400; color: {p.text_primary}; }}
    QLabel[role="body-sm"]     {{ font-size: 12px; font-weight: 400; color: {p.text_secondary}; }}
    QLabel[role="label-md"]    {{ font-size: 12px; font-weight: 500; color: {p.text_secondary}; }}
    QLabel[role="label-caps"]  {{
        font-size: 11px; font-weight: 700; color: {p.accent};
        letter-spacing: 0.6px;
    }}
    QLabel[role="card-title"]  {{ font-size: 20px; font-weight: 700; letter-spacing: -0.2px; }}
    QLabel[role="card-desc"]   {{ font-size: 13px; color: {p.text_secondary}; }}

    /* --- Botones de la barra de acciones --- */
    QToolButton#AccionBarra {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: {RADIUS_CONTROL}px;
        padding: 5px 13px;
        color: {p.text_primary};
        font-size: 12px;
        font-weight: 600;
    }}
    QToolButton#AccionBarra:hover {{ background-color: {p.control_hover}; }}
    QToolButton#AccionBarra:pressed {{ background-color: {p.elevated_max}; }}
    QToolButton#AccionBarra:focus {{ border: 1px solid {p.accent}; }}
    QToolButton#AccionBarra:disabled {{ color: {p.text_secondary}; }}

    /* --- Separador vertical --- */
    QFrame#Separador {{ color: {p.border}; background-color: {p.border}; }}

    /* --- Control segmentado (estilo macOS: pista hundida, pulgar elevado) --- */
    QFrame#ControlSegmentado {{
        background-color: {p.bg};
        border-radius: {RADIUS_CONTROL + 1}px;
        border: 1px solid {p.border_subtle};
    }}
    QPushButton#SegmentoPestana {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: {RADIUS_CONTROL - 1}px;
        padding: 5px 9px;
        font-size: 12px;
        font-weight: 600;
        color: {p.text_secondary};
    }}
    QPushButton#SegmentoPestana:checked {{
        background-color: {p.elevated};
        border: 1px solid {glass_edge};
        color: {p.text_primary};
    }}
    QPushButton#SegmentoPestana:focus {{ border: 1px solid {p.accent}; }}

    /* --- Botones genericos --- */
    QPushButton {{
        background-color: {p.control_fill};
        border: 1px solid {p.border};
        border-radius: {RADIUS_CONTROL}px;
        padding: 8px 14px;
        font-size: 13px;
        color: {p.text_primary};
    }}
    QPushButton:hover {{ background-color: {p.control_hover}; }}
    QPushButton:pressed {{ background-color: {p.elevated_max}; }}
    QPushButton:focus {{ border-color: {p.accent}; }}
    QPushButton#Primario {{
        background-color: {p.accent};
        border: 1px solid transparent;
        color: {p.on_accent};
        font-weight: 600;
        padding: 8px 17px;
    }}
    QPushButton#Primario:hover {{ background-color: {p.accent_strong}; color: #FFFFFF; }}
    QPushButton#Primario:pressed {{ background-color: {p.accent_strong}; color: #FFFFFF; }}
    QPushButton#Primario:focus {{ border: 1px solid {p.on_accent}; }}
    /* Acción destructiva (restablecer): texto rojo sin relieve, lavado al pasar. */
    QPushButton#BotonReset {{
        background-color: transparent;
        border: 1px solid transparent;
        border-radius: {RADIUS_CONTROL}px;
        padding: 8px 14px;
        font-size: 13px;
        font-weight: 600;
        color: {p.error};
    }}
    QPushButton#BotonReset:hover {{ background-color: {error_tint}; }}
    QPushButton#BotonReset:pressed {{ background-color: {error_tint_strong}; }}
    QPushButton#BotonReset:focus {{ border: 1px solid {p.error}; }}
    /* Atajo asignado: cápsula sutil con tipografía del sistema (sin monoespaciada). */
    QPushButton#BotonAsignacion {{
        min-width: {ASSIGN_BUTTON_MIN_WIDTH}px;
        background-color: {p.elevated_max};
        border: 1px solid {p.border_subtle};
        border-radius: {RADIUS_CHIP}px;
        padding: 6px 8px;
        font-size: 12px;
        font-weight: 500;
        color: {p.text_primary};
    }}
    QPushButton#BotonAsignacion:hover {{
        background-color: {accent_tint};
        border-color: {p.accent};
    }}
    QPushButton#BotonAsignacion:focus {{ border-color: {p.accent}; }}
    QPushButton#BotonAsignacion[listening="true"] {{
        background-color: {p.accent};
        border: 1px solid {p.accent};
        color: {p.on_accent};
    }}

    /* --- ComboBox --- */
    QComboBox {{
        background-color: {p.control_fill};
        border: 1px solid {p.border};
        border-radius: {RADIUS_CONTROL}px;
        padding: 7px 10px;
        font-size: 13px;
        min-height: 18px;
    }}
    QComboBox:hover {{ background-color: {p.control_hover}; }}
    QComboBox:focus {{ border-color: {p.accent}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{
        background-color: {p.elevated};
        border: 1px solid {p.border};
        border-radius: {RADIUS_CONTROL}px;
        padding: 4px;
        outline: none;
        selection-background-color: {p.accent};
        selection-color: {p.on_accent};
    }}
    QComboBox QAbstractItemView::item {{
        padding: 5px 8px;
        border-radius: {RADIUS_CONTROL - 2}px;
    }}
    /* Oculta el "✓" por defecto del elemento actual (estilo macOS limpio). */
    QComboBox QAbstractItemView::indicator {{ width: 0px; height: 0px; }}
    QToolButton#BotonRefrescar {{
        background-color: {p.control_fill};
        border: 1px solid {p.border};
        border-radius: {RADIUS_CONTROL}px;
        padding: 7px;
    }}
    QToolButton#BotonRefrescar:hover {{ background-color: {p.control_hover}; }}
    QToolButton#BotonRefrescar:focus {{ border-color: {p.accent}; }}

    /* --- Scroll area --- */
    QScrollArea {{ border: none; background: transparent; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QScrollBar:vertical {{
        background: transparent; width: 12px; margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {p.elevated_max}; border-radius: 4px; min-height: 32px;
        margin: 0 3px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {p.text_secondary}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}

    /* --- Tarjetas de estado --- */
    QFrame#TarjetaEstado {{
        background-color: transparent;
    }}
    /* IconoTarjeta ahora es un pixmap de icono de línea (ver widgets/icons.py). */
    QFrame#Pildora {{
        background-color: {p.elevated_max};
        border-radius: {RADIUS_CHIP}px;
        padding: 3px 12px;
    }}
    QLabel[role="pildora"] {{ font-size: 11px; font-weight: 600; color: {p.text_secondary}; }}

    /* --- Lista de mapeo "inset grouped" (un contenedor, filas con hairline) --- */
    QFrame#GrupoMapeo {{
        background-color: {p.elevated};
        border: 1px solid {p.border_subtle};
        border-radius: {RADIUS_GROUP}px;
    }}
    QFrame#FilaMapeo {{ background-color: transparent; border: none; }}
    QFrame#SeparadorFila {{ background-color: {p.border}; border: none; }}
    QLabel#IconoEntrada {{ font-size: 16px; }}

    /* --- Ilustracion / contenedores redondeados --- */
    QFrame#ContenedorIlustracion {{
        background-color: {p.elevated};
        border: 1px solid {p.border_subtle};
        border-radius: {RADIUS_GROUP}px;
    }}

    /* --- Biblioteca de ROMs (cuadrícula en el escenario) --- */
    QListWidget#Biblioteca {{
        background: transparent;
        border: none;
        outline: none;
    }}
    QListWidget#Biblioteca::item {{
        background-color: {p.elevated};
        border: 1px solid {p.border_subtle};
        border-radius: {RADIUS_GROUP}px;
        margin: 6px;
        padding: 10px 6px;
        color: {p.text_primary};
        font-size: 13px;
        font-weight: 600;
    }}
    QListWidget#Biblioteca::item:hover {{
        background-color: {p.control_hover};
    }}
    QListWidget#Biblioteca::item:selected {{
        background-color: {accent_tint};
        border: 1px solid {p.accent};
        color: {p.text_primary};
    }}
    """
