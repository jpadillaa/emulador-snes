# Soporte real de gamepad — Diseño

Fecha: 2026-06-26
Estado: aprobado para implementación

## Objetivo

Permitir jugar con un mando físico (incluidos controles Bluetooth en macOS),
con sus botones **remapeables** desde el panel existente y perfiles
independientes por dispositivo. Hoy solo funciona el teclado y la UI de
dispositivos/conexión es decorativa (`DEFAULT_DEVICES = ["Keyboard"]`, siempre
"Conectado").

## Decisiones de alcance

- **Backend:** `pygame.joystick` (ya es dependencia). `QtGamepad` no existe en
  PySide6 6.11; SDL en macOS exige el hilo principal para el *event pump*, así
  que no se usan hilos. Se usa el joystick **crudo** (no la API experimental
  `pygame._sdl2.controller`).
- **Remapeo + perfiles por dispositivo** (Q1): cada dispositivo tiene su propio
  perfil de asignaciones, editable desde el panel. El teclado conserva su perfil.
- **Enrutamiento OR-combine** (Q2): el teclado **siempre** alimenta el juego;
  además, el mando activo envía sus entradas. Una entrada SNES está activa si la
  produce el teclado **o** el mando. Nunca te quedas sin control si el mando se
  desconecta.
- **Un solo jugador (puerto 0).** El núcleo y la UI son de un puerto;
  multijugador queda fuera de alcance (YAGNI).
- **Stick analógico izquierdo:** espeja el D-Pad por defecto (zona muerta ~0.5),
  como conveniencia en la capa de lectura, independiente de los bindings.

## Arquitectura

Enfoque elegido: un servicio aislado que encapsula todo pygame, espejo de
`InputService`/`SaveService`, sin tocar `SessionController` (se respeta la
disciplina de aislamiento del CLAUDE.md).

### `GamepadService(QObject)` — `snes_ui/services/gamepad_service.py` (nuevo)

- Inicializa pygame con `SDL_VIDEODRIVER=dummy` + `pygame.joystick.init()`. Si
  pygame falla al importar/iniciar, **degrada a no-op** (sin mandos; el teclado
  sigue funcionando) — mismo patrón de degradación que el audio.
- `QTimer` propio (~60 Hz) siempre activo tras `start()`. En cada tick hace
  `pygame.event.pump()`, procesa hot-plug y, según el modo:
  - **Modo juego** (sesión RUNNING): lee el estado del mando activo, lo traduce
    con su perfil y emite el conjunto de entradas SNES presionadas.
  - **Modo captura** (una fila escucha y el dispositivo activo es un mando):
    emite la siguiente entrada física cruda como `Binding`, sin alimentar el
    juego.
- **Señales:** `devices_changed(list[str])`, `connection_changed(ConnectionState)`,
  `pressed_changed(set[str])`, `binding_captured(Binding)`.
- **Costura de pruebas `_PadBackend`:** la lectura del joystick pasa por una
  capa fina que en tests se sustituye por un mando falso con estado guionado.

### Enrutamiento en `MainWindow`

Mantiene `_kbd_pressed: set[str]` y `_pad_pressed: set[str]`. Cualquier cambio
(evento de tecla o `pressed_changed`) llama a un único `_recompute_inputs()`:

1. `union = _kbd_pressed | _pad_pressed`
2. actualiza el diagrama en vivo con `union`
3. para cada entrada SNES: `core.set_input(retro_id, input_key in union)`

Así una tecla soltada no apaga un botón que el mando aún mantiene, y viceversa.
Los handlers de teclado actualizan `_kbd_pressed` y llaman a `_recompute_inputs()`;
la señal del mando actualiza `_pad_pressed` e igual.

## Modelo de datos

### `Binding` (en `input_service.py`)

```python
@dataclass(frozen=True)
class Binding:
    kind: str    # "key" | "button" | "hat" | "axis"
    code: int    # código Qt / índice de botón / índice de hat / índice de eje
    value: int = 0   # hat: dirección empaquetada; axis: signo (-1/+1); ignorado en key/button
```

`label()` produce el texto de la fila: `"Tecla: X"`, `"Botón 0"`, `"D-Pad ↑"`,
`"Eje 1 +"`. El binding de teclado es `Binding("key", qt_code)`, generalizando el
modelo del trabajo previo (#1) sin perder comportamiento.

Empaquetado de `value` para hat: las 8 direcciones de un hat SDL son pares
`(x, y)` con x,y ∈ {-1,0,1}; se empaquetan como `(x + 1) * 3 + (y + 1)` (0–8).

### Perfiles por dispositivo — `MappingProfiles`

Gestiona `dict[device_key -> dict[input_key -> Binding]]`:

- `device_key`: `"keyboard"` para el teclado; el **GUID SDL**
  (`joystick.get_guid()`, estable por modelo) para cada mando. El nombre visible
  viene de `get_name()`.
- El teclado siempre tiene perfil (default = `DEFAULT_KEYBOARD` como bindings
  `key`).
- Cada mando nuevo recibe un **perfil por defecto** estilo estándar (Xbox):
  A=botón 0, B=1, X=2, Y=3, L=4, R=5, Select=6, Start=7, D-Pad = hat 0. Con
  mandos no estándar el default puede quedar corrido; se remapea y queda guardado
  por GUID.
- Métodos: `profile_for(device_key)`, `binding(device_key, input_key)`,
  `assign(device_key, input_key, binding)`, `reset(device_key)`,
  `input_for(device_key, ...)` para la búsqueda inversa en juego.

### Persistencia — `settings.py`

JSON anidado por dispositivo:
`{ device_key: { input_key: {kind, code, value} } }`.

**Migración:** el formato previo (#1) era un dict plano `{input_key: int}`; se
reinterpreta como el perfil `"keyboard"` con bindings `key`. Lo no reconocido se
descarta (igual que ya hace #1).

## Flujos

### Captura (remapeo)

Al entrar una fila en escucha, `MainWindow` mira el dispositivo activo:
- **Teclado** → el próximo evento de tecla asigna `Binding("key", code)` (como hoy).
- **Mando** → se pone `GamepadService` en modo captura; la próxima entrada física
  (botón / hat / eje pasada la zona muerta) llega vía `binding_captured(Binding)`
  y se asigna a la fila. Escape cancela (mecanismo ya existente).

`MappingRow`/panel no cambian de API: solo cambia la fuente del texto, que ahora
es `binding.label()`.

### Hot-plug y conexión (reutiliza el indicador existente)

- Mando conectado → se añade a la lista (`devices_changed`); si no había mando
  activo, se **auto-selecciona**; indicador `CONNECTED`.
- Mando activo desconectado → `DISCONNECTED`; el enrutamiento cae al teclado (que
  nunca se apagó). No se pausa el juego.
- "Keyboard" siempre presente en el combo.

### Stick analógico

El eje del stick izquierdo (índices 0/1) se convierte a direcciones del D-Pad con
zona muerta ~0.5 en la capa de lectura del `GamepadService`, sumándose (OR) a lo
que produzca el hat/bindings. No participa en el modelo de bindings 1:1.

## Manejo de errores

- Import/init de pygame falla → `GamepadService` no-op; el teclado intacto.
- Error leyendo un mando (desconexión a media lectura) → capturar, marcar
  `DISCONNECTED`, re-enumerar.
- GUID no disponible en algún backend → caer al nombre del dispositivo como
  `device_key`.

## Estrategia de pruebas (sin hardware)

Mediante la costura `_PadBackend` con un mando falso de estado guionado:

- Traducción estado→entradas SNES con un perfil dado.
- OR-combine teclado+mando en `MainWindow` (`_recompute_inputs`).
- Captura: entrada física cruda → `Binding` correcto (botón/hat/eje).
- `Binding` round-trip JSON y migración del formato plano de #1.
- Perfil por defecto por dispositivo; perfiles separados por GUID.
- Stick → D-Pad con zona muerta.
- Enumeración con 0 mandos no rompe; hot-plug simulado por eventos inyectados.
- Smoke headless: `GamepadService` real (0 mandos) + `MainWindow`.

## Archivos afectados

- **Nuevo:** `snes_ui/services/gamepad_service.py`.
- **Modificados:** `snes_ui/services/input_service.py` (`Binding`,
  `MappingProfiles`, defaults de mando), `snes_ui/widgets/control_panel.py`
  (usar `binding.label()`, mostrar perfil del dispositivo activo),
  `snes_ui/main_window.py` (enrutamiento OR, captura por mando, conexión),
  `snes_ui/settings.py` (persistencia anidada + migración).
- **Sin cambios:** `snes_ui/core/session.py`.

## Fuera de alcance

- Multijugador (puerto 1+).
- API `pygame._sdl2.controller` / base de datos de mapeos estándar.
- Rumble / vibración.
- Reasignación de la zona muerta desde la UI (constante por ahora).
