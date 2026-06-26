"""Reproduccion de audio del nucleo de emulacion (QtMultimedia).

Recibe muestras PCM S16 estereo intercaladas (L,R,L,R...) generadas por el
nucleo y las reproduce en tiempo real mediante ``QAudioSink`` en modo push.

Diseño:
- Todo ocurre en el hilo principal. El nucleo genera audio dentro de
  ``retro_run`` (invocado por el QTimer de la sesion); ``enqueue`` acumula y
  ``flush`` entrega al dispositivo. ``QAudioSink`` reproduce en su propio hilo
  de backend, por lo que ``write`` solo copia y retorna: la GUI nunca se bloquea.
- La latencia se acota con el tamaño de buffer del sink y un tope de backlog;
  ``bytesFree`` evita escribir mas de lo que el dispositivo puede aceptar.

No introduce dependencias nuevas: QtMultimedia viene con PySide6.
"""
from __future__ import annotations

from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices

BYTES_PER_FRAME = 4          # 2 canales * 2 bytes (S16)
DEFAULT_LATENCY_MS = 100     # objetivo de latencia (tamaño de buffer del sink)
MAX_BACKLOG_MS = 200         # backlog maximo acumulado antes de descartar


class AudioPlayer:
    """Salida de audio en tiempo real para muestras PCM S16 estereo."""

    def __init__(self, sample_rate: float, latency_ms: int = DEFAULT_LATENCY_MS) -> None:
        fmt = QAudioFormat()
        fmt.setSampleRate(int(sample_rate))
        fmt.setChannelCount(2)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        device = QMediaDevices.defaultAudioOutput()
        if device is None or device.isNull():
            raise RuntimeError("No hay dispositivo de salida de audio disponible.")
        if not device.isFormatSupported(fmt):
            fmt = device.preferredFormat()

        self._bytes_per_sec = int(sample_rate) * BYTES_PER_FRAME
        self._sink = QAudioSink(device, fmt)
        self._sink.setBufferSize(max(2048, self._bytes_per_sec * latency_ms // 1000))

        self._io = None                       # QIODevice de escritura (push mode)
        self._pending = bytearray()
        self._cap = self._bytes_per_sec * MAX_BACKLOG_MS // 1000
        self._active = False

    def start(self) -> None:
        """Arranca o reanuda la reproduccion."""
        if self._io is None:
            self._io = self._sink.start()      # modo push: devuelve el QIODevice
        else:
            self._sink.resume()
        self._active = self._io is not None

    def enqueue(self, data: bytes) -> None:
        """Acumula muestras generadas por el nucleo durante el frame."""
        if not self._active:
            return
        self._pending += data
        # Acota la latencia: si el video va por delante, descarta lo mas viejo.
        excess = len(self._pending) - self._cap
        if excess > 0:
            del self._pending[:excess]

    def flush(self) -> None:
        """Entrega al dispositivo tanto como acepte sin bloquear."""
        if not self._active or self._io is None or not self._pending:
            return
        free = self._sink.bytesFree()
        if free <= 0:
            return
        n = min(free, len(self._pending))
        self._io.write(bytes(self._pending[:n]))
        del self._pending[:n]

    def pause(self) -> None:
        if self._active:
            self._sink.suspend()
            self._active = False

    def resume(self) -> None:
        if self._io is not None:
            self._sink.resume()
            self._active = True

    def stop(self) -> None:
        self._active = False
        self._pending.clear()
        try:
            self._sink.stop()
        except Exception:
            pass
        self._io = None
