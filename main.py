"""Punto de entrada de SNES Emulator (interfaz grafica PySide6).

Configura el escalado HiDPI, crea la QApplication, define identidad para
QSettings y muestra la ventana principal. La logica de emulacion no se
implementa aqui: la UI opera contra un nucleo simulado a traves del
adaptador, listo para sustituirse por el nucleo real.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import QApplication

from snes_ui.main_window import MainWindow
from snes_ui.settings import APP, ORG
from snes_ui.theme import system_font_family


def main() -> int:
    # Politica de redondeo del factor de escala que evita bordes borrosos en
    # pantallas HiDPI / Retina.
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(APP)
    app.setOrganizationName(ORG)
    app.setApplicationDisplayName("SNES Emulator")
    # Fija la fuente base a una del sistema antes de crear cualquier widget,
    # evitando que el backend recurra al alias inexistente "Sans Serif".
    app.setFont(QFont(system_font_family()))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
