"""Configuración de pytest: QApplication offscreen y QSettings aislados."""
import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

# Redirige QSettings a un directorio temporal (formato INI) para que los tests
# no lean ni escriban las preferencias reales del usuario y sean herméticos.
QSettings.setDefaultFormat(QSettings.Format.IniFormat)
QSettings.setPath(
    QSettings.Format.IniFormat, QSettings.Scope.UserScope, tempfile.mkdtemp()
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
