# Visión general

Este documento define la interfaz de usuario completa de **SNES Emulator**, una aplicación de escritorio de emulación SNES construida con Python y PySide6, orientada a macOS y Windows con soporte HiDPI y Retina. La especificación está pensada como entrada directa para agentes de programación. Es determinística y describe jerarquía de widgets, contenedores, relaciones padre e hijo, estados visuales y comportamientos esperados sin describir el núcleo de emulación ni la arquitectura interna.

La interfaz se organiza en dos grandes regiones horizontales dentro de una ventana única. A la izquierda, un área principal fluida que contiene el escenario de juego y una barra de acciones inferior. A la derecha, un panel auxiliar de ancho fijo dedicado a la configuración y visualización del control. La estética sigue la línea utilitaria y nativa descrita en los artefactos de referencia, con tipografía sistémica, jerarquía cromática por tonos y baja ornamentación.

## Reconciliación de artefactos

Existen dos diferencias entre el wireframe y la exportación de Google Stitch. Se resuelven así.

| Aspecto | Wireframe | Google Stitch | Decisión aplicada |
|---|---|---|---|
| Barra lateral izquierda de navegación | Ausente | Presente con Library, Settings, Controls, Performance | Se excluye. El wireframe gobierna la distribución visual. La aplicación tiene solo dos regiones en el cuerpo |
| Tema cromático | Claro | Oscuro | Se definen ambos temas. El tema sigue la apariencia del sistema. El tema claro es la referencia del wireframe y el oscuro toma la paleta de Stitch |
| Barra de título | Controles nativos macOS dibujados | Controles dibujados como widgets | Se usa el marco nativo del sistema operativo. No se reimplementan controles de ventana personalizados |
| Filas de mapeo Select y Start | Presentes | Ausentes en el HTML | Se incluyen. El conjunto completo tiene doce filas |

El wireframe gobierna estructura, distribución espacial y jerarquía. La exportación de Stitch gobierna componentes, estados, interacciones y comportamiento funcional.

---

# Objetivos UX

- Mantener el juego como elemento central. La interfaz se repliega para que el escenario domine el espacio.
- Reducir la carga cognitiva con una jerarquía visual clara y agrupación explícita de funciones.
- Ofrecer acceso inmediato a las acciones principales desde una barra siempre visible mientras hay un juego activo.
- Garantizar apariencia profesional y coherencia con las convenciones de cada sistema operativo.
- Asegurar legibilidad y alineación precisa en pantallas HiDPI y Retina.
- Proporcionar retroalimentación visual inequívoca para cada estado del sistema, incluidos los estados vacío, cargando, ejecutando, pausado y error.

---

# Layout principal

## Estructura general de la ventana

La ventana principal usa el marco nativo del sistema. El título de la ventana es **SNES Emulator**. El cuerpo de la ventana se divide en un eje horizontal con dos regiones.

```
VentanaPrincipal (marco nativo del SO)
└── WidgetCentral
    └── LayoutCuerpo (horizontal)
        ├── AreaPrincipal            [expansible, factor de estiramiento 1]
        │   ├── EscenarioJuego        [expansible, factor de estiramiento 1]
        │   └── BarraAcciones         [altura fija 88 px]
        └── PanelControl              [ancho fijo 320 px]
```

## Distribución espacial

- Márgenes externos del cuerpo de 16 px en los cuatro lados.
- Separación de 16 px entre el área principal y el panel de control.
- El área principal absorbe todo el ancho disponible. El panel de control conserva su ancho.
- Dentro del área principal el escenario ocupa el espacio vertical disponible y la barra de acciones se ancla abajo con altura fija.

## Comportamiento al redimensionar

- El escenario de juego crece y se reduce con la ventana manteniendo la relación de aspecto del contenido mediante letterboxing.
- El panel de control mantiene su ancho fijo de 320 px. Toda variación de ancho de la ventana la absorbe el área principal.
- La barra de acciones conserva su altura de 88 px y centra horizontalmente su grupo de botones.
- Por debajo del tamaño mínimo de ventana se activa el desplazamiento vertical del panel de control. El escenario nunca queda con un ancho útil menor a 480 px.

## Tamaños de referencia

| Parámetro | Valor |
|---|---|
| Tamaño inicial de ventana | 1360 x 860 px |
| Tamaño mínimo de ventana | 1024 x 700 px |
| Ancho del panel de control | 320 px fijo |
| Altura de la barra de acciones | 88 px |
| Padding interno del escenario | 16 px |
| Relación de aspecto del escenario | 4:3 por defecto |

---

# Jerarquía de componentes

```
VentanaPrincipal  [QMainWindow]
└── WidgetCentral  [QWidget]
    └── LayoutCuerpo  [QHBoxLayout, margins 16, spacing 16]
        ├── AreaPrincipal  [QWidget, QVBoxLayout, spacing 16]
        │   ├── EscenarioJuego  [QFrame -> QStackedWidget]
        │   │   ├── VistaVacio        [QWidget]
        │   │   ├── VistaCargando     [QWidget]
        │   │   ├── VistaEjecucion     [QWidget que contiene la SuperficieVideo]
        │   │   ├── VistaPausa         [QWidget]
        │   │   └── VistaError         [QWidget]
        │   └── BarraAcciones  [QFrame, QHBoxLayout]
        │       ├── BotonCargarJuego        [QToolButton]
        │       ├── Separador               [QFrame VLine]
        │       ├── BotonGuardarPartida     [QToolButton]
        │       ├── Separador               [QFrame VLine]
        │       ├── BotonCargarPartida      [QToolButton]
        │       ├── Separador               [QFrame VLine]
        │       ├── BotonSalir              [QToolButton]
        │       ├── Separador               [QFrame VLine]
        │       └── BotonPantallaCompleta   [QToolButton]
        └── PanelControl  [QFrame, QVBoxLayout, spacing 0]
            ├── ControlSegmentado  [QFrame, QHBoxLayout, QButtonGroup exclusivo]
            │   ├── PestanaConfiguracion           [QPushButton checkable]
            │   └── PestanaVisualizacionControl    [QPushButton checkable]
            ├── ContenidoPanel  [QStackedWidget dentro de QScrollArea]
            │   ├── VistaConfiguracion  [QWidget, QVBoxLayout, spacing 32]
            │   │   ├── SeccionControlActual  [QWidget]
            │   │   │   ├── EncabezadoSeccion         [QLabel estilo label-caps]
            │   │   │   ├── FilaSelector              [QHBoxLayout]
            │   │   │   │   ├── SelectorControl        [QComboBox]
            │   │   │   │   └── BotonRefrescar         [QToolButton]
            │   │   │   └── FilaEstadoConexion        [QHBoxLayout]
            │   │   │       ├── IndicadorEstado        [QLabel punto de color]
            │   │   │       └── EtiquetaEstado         [QLabel]
            │   │   └── SeccionAsignacionBotones  [QWidget]
            │   │       ├── EncabezadoSeccion           [QLabel estilo label-caps]
            │   │       ├── IlustracionControl          [QLabel o QSvgWidget]
            │   │       └── ListaMapeo  [QWidget, QVBoxLayout, spacing 8]
            │   │           └── FilaMapeo x12  [QWidget, QHBoxLayout]
            │   │               ├── IconoEntrada     [QLabel]
            │   │               ├── NombreEntrada    [QLabel, stretch]
            │   │               └── BotonAsignacion  [QPushButton]
            │   └── VistaVisualizacionControl  [QWidget, QVBoxLayout]
            │       ├── EtiquetaControlActivo   [QLabel]
            │       └── DiagramaControlVivo     [QSvgWidget o QWidget pintado]
            └── PieControl  [QWidget, QVBoxLayout]
                └── BotonRestablecer  [QPushButton, ancho completo]
```

---

# Componentes de la interfaz

## Escenario de juego

El escenario es el componente central del área principal. Es un contenedor con borde de 1 px, esquinas redondeadas de 12 px y un `QStackedWidget` interno que conmuta entre las cinco vistas de estado. La superficie de video ocupa la vista de ejecución y mantiene la relación de aspecto 4:3 con letterboxing.

### Modos de visualización

El escenario admite cuatro modos de escalado seleccionables desde el menú de aplicación.

| Modo | Comportamiento |
|---|---|
| Ajuste a ventana | Escala el contenido al máximo manteniendo la relación 4:3 con letterboxing. Modo por defecto |
| Escalado entero | Escala por múltiplos enteros del tamaño nativo para evitar artefactos de interpolación |
| Relación original | Aplica la relación de píxel 8:7 propia del hardware |
| Estirar | Llena el escenario ignorando la relación de aspecto |

### Tarjeta de estado

Las vistas vacío, cargando, pausa y error muestran una tarjeta centrada con una estructura común. Un icono superior, un título, una línea descriptiva y, cuando aplica, una píldora con el sistema o una acción primaria. La vista de ejecución reemplaza la tarjeta por la superficie de video.

## Barra de acciones

Contenedor con borde de 1 px y esquinas redondeadas de 12 px, anclado bajo el escenario, con altura fija de 88 px. Centra horizontalmente un grupo de cinco botones de acción separados por divisores verticales de 40 px de alto. Cada botón usa disposición vertical con icono arriba, etiqueta principal en el medio y etiqueta secundaria abajo.

| Acción | Etiqueta principal | Etiqueta secundaria | Icono recomendado | Atajo macOS | Atajo Windows |
|---|---|---|---|---|---|
| Cargar juego | Cargar juego | Abrir ROM | folder_open | Cmd O | Ctrl O |
| Guardar partida | Guardar partida | Guardar estado | save | Cmd S | Ctrl S |
| Cargar partida | Cargar partida | Cargar estado | download | Cmd L | Ctrl L |
| Salir | Salir | Volver al menú | logout | Cmd W | Ctrl W |
| Pantalla completa | Pantalla completa | Alternar | fullscreen | Cmd Ctrl F | F11 |

Comportamiento de cada acción.

- **Cargar juego** abre el diálogo de selección de ROM y dispara el flujo de carga.
- **Guardar partida** crea un estado guardado de la sesión activa y muestra confirmación.
- **Cargar partida** abre la selección de estados guardados y restaura el seleccionado.
- **Salir** cierra la sesión de juego activa y devuelve la interfaz al estado vacío.
- **Pantalla completa** alterna entre ventana y pantalla completa.

En el estado vacío, las acciones Guardar partida, Cargar partida y Salir permanecen deshabilitadas. Solo Cargar juego y Pantalla completa están activas.

## Panel de control

Panel derecho de ancho fijo. Tres regiones verticales. Un control segmentado superior, un cuerpo desplazable y un pie con el botón de restablecer.

### Control segmentado

Dos opciones mutuamente exclusivas con apariencia de control segmentado nativo. Pista hundida y pulgar activo deslizante. La opción activa por defecto es Configuración.

- **Configuración** muestra el selector de control, la ilustración del mando y la lista de asignación de botones.
- **Visualización del control** muestra un diagrama del mando ampliado que resalta las entradas presionadas en tiempo real. Esta vista es de solo lectura.

### Sección Control actual

Encabezado en mayúsculas con estilo label-caps. Una fila con un `QComboBox` que ocupa el ancho disponible y un botón de refrescar a su derecha. Bajo la fila, un indicador de estado de conexión compuesto por un punto de color y una etiqueta de texto.

Opciones iniciales del selector.

- Xbox Wireless Controller
- DualSense Wireless Controller
- Keyboard

Estados de conexión.

| Estado | Color del punto | Etiqueta |
|---|---|---|
| Conectado | Verde sistema | Conectado |
| Desconectado | Gris outline | Desconectado |
| Reconectando | Ámbar | Reconectando |

El botón de refrescar vuelve a enumerar los dispositivos disponibles y actualiza el selector y el indicador.

### Sección Asignación de botones

Encabezado en mayúsculas con estilo label-caps. Una ilustración del mando SNES con relación de aspecto 2:1 dentro de un contenedor redondeado. Debajo, la lista de mapeo con doce filas. Cada fila tiene un icono de entrada, el nombre de la entrada lógica del SNES alineado a la izquierda y un botón de asignación de ancho mínimo 104 px alineado a la derecha que muestra la entrada física asignada.

| Entrada SNES | Icono | Asignación inicial |
|---|---|---|
| D-Pad Arriba | keyboard_arrow_up | Eje Y- |
| D-Pad Abajo | keyboard_arrow_down | Eje Y+ |
| D-Pad Izquierda | keyboard_arrow_left | Eje X- |
| D-Pad Derecha | keyboard_arrow_right | Eje X+ |
| A | círculo A | Botón B |
| B | círculo B | Botón A |
| X | círculo X | Botón Y |
| Y | círculo Y | Botón X |
| Select | keyboard | Botón View |
| Start | keyboard | Botón Menu |
| L | keyboard_tab | Botón LB |
| R | keyboard_tab invertido | Botón RB |

Comportamiento de la fila de mapeo. Al pulsar el botón de asignación, este entra en estado de escucha y muestra el texto **Presiona un botón**. La siguiente entrada física detectada se asigna a esa fila y el botón vuelve a su estado normal mostrando la nueva asignación. La tecla Escape cancela la escucha sin cambiar la asignación.

### Pie del panel

Botón **Restablecer configuración** de ancho completo. Revierte todas las asignaciones a sus valores iniciales tras una confirmación.

---

# Flujos de interacción

## Flujo de carga de juego

1. El usuario activa Cargar juego desde la barra de acciones o el atajo.
2. Se abre un `QFileDialog` filtrado a extensiones de ROM admitidas, entre ellas sfc y smc.
3. Si el usuario cancela, el estado de la interfaz no cambia.
4. Si selecciona un archivo, la interfaz pasa al estado cargando y muestra el nombre del archivo.
5. Si la validación de la ROM falla, la interfaz pasa al estado error con un mensaje claro y un botón para reintentar.
6. Si la validación es correcta, la interfaz transiciona al estado ejecutando, habilita Guardar partida, Cargar partida y Salir, y muestra la superficie de video.

## Flujo de guardado

1. El usuario activa Guardar partida con una sesión de juego activa.
2. Se genera el estado guardado de la sesión.
3. Al completarse, aparece una confirmación breve no bloqueante, por ejemplo un toast o un cambio temporal del icono a verificación, durante unos dos segundos.
4. Si el guardado falla por permisos o espacio, se muestra un diálogo de error con la causa y una opción para reintentar.
5. La acción está deshabilitada cuando no hay sesión activa.

## Flujo de carga de partida

1. El usuario activa Cargar partida con o sin sesión activa.
2. Se abre un selector de estados guardados que lista los estados disponibles para la ROM en curso, con marca temporal y miniatura cuando exista.
3. Si no hay estados, el selector muestra un estado vacío con el mensaje correspondiente.
4. Al elegir un estado, la sesión se restaura y la interfaz vuelve o permanece en el estado ejecutando.
5. Una confirmación breve indica la restauración exitosa. Un fallo muestra un diálogo de error.

## Flujo de pantalla completa

1. El usuario activa Pantalla completa por botón, atajo o el control nativo de la ventana en macOS.
2. La ventana entra en pantalla completa. El panel de control y la barra de acciones se ocultan. El escenario llena toda la pantalla.
3. Una barra de acciones superpuesta aparece al mover el cursor cerca del borde inferior y se autooculta tras 2,5 segundos de inactividad.
4. La tecla Escape o el atajo de pantalla completa devuelven la ventana a su estado anterior.
5. Al salir, el escenario, el panel de control y la barra de acciones recuperan su tamaño y posición previos.

## Flujo de salida del juego

1. El usuario activa Salir con una sesión activa.
2. Si hay progreso sin guardar, se muestra una confirmación que ofrece guardar, salir sin guardar o cancelar.
3. Al confirmar, la sesión de juego se cierra.
4. El escenario limpia la superficie de video y vuelve al estado vacío.
5. Las acciones dependientes de sesión se deshabilitan de nuevo.

---

# Estados de la interfaz

El `QStackedWidget` del escenario expone exactamente cinco vistas. La pantalla completa es un modo de presentación que se superpone a cualquiera de ellas.

## Estado vacío

Activo cuando no hay ROM cargada. La tarjeta central muestra un icono atenuado de mando, el título **NINGÚN JUEGO CARGADO**, una línea de ayuda que invita a cargar una ROM y un botón primario Cargar juego. Las acciones dependientes de sesión están deshabilitadas.

## Estado cargando

Activo durante la apertura y validación de una ROM. La tarjeta muestra un indicador de progreso indeterminado, el título **CARGANDO** y el nombre del archivo en proceso. La interfaz bloquea nuevas cargas hasta finalizar.

## Estado ejecutando

Sesión activa. La superficie de video llena el escenario manteniendo la relación de aspecto. De forma opcional, al iniciar la sesión, una breve presentación de título con el nombre del juego y la píldora del sistema aparece y se desvanece. La barra de acciones queda completamente habilitada.

## Estado pausado

Emulación suspendida. Sobre el último fotograma se aplica una capa traslúcida oscura. Una tarjeta central muestra el icono de pausa, el título **PAUSA** y una indicación para reanudar. La reanudación se realiza con la barra de acciones, un atajo o un clic sobre el escenario.

## Estado error

Activo ante fallos de carga, configuración o dispositivos. La tarjeta muestra un icono de error en color de error, un título corto, un mensaje descriptivo con la causa y una o dos acciones, por ejemplo Reintentar y Cerrar. El error no debe escalar a estados ambiguos. Siempre ofrece una salida clara hacia el estado vacío.

## Estado pantalla completa

Modo de presentación. El escenario ocupa la pantalla completa. El panel de control y la barra de acciones fija desaparecen. La barra de acciones superpuesta provee acceso a las funciones y se autooculta. La asignación de controles permanece vigente sin cambios.

---

# Componentes PySide6 recomendados

| Componente de UI | Widget principal | Layout | Hijos clave | Propósito funcional |
|---|---|---|---|---|
| Ventana principal | QMainWindow | n/a | WidgetCentral | Contenedor raíz con marco nativo, menús y restauración de geometría |
| Cuerpo | QWidget | QHBoxLayout | AreaPrincipal, PanelControl | Divide la ventana en área principal y panel de control |
| Área principal | QWidget | QVBoxLayout | EscenarioJuego, BarraAcciones | Apila el escenario expansible sobre la barra de acciones fija |
| Escenario de juego | QFrame con QStackedWidget interno | QStackedLayout | Cinco vistas de estado | Conmuta entre estados visuales y aloja la superficie de video |
| Superficie de video | QWidget dedicado a presentación | n/a | n/a | Recibe el fotograma renderizado. Su contenido interno queda fuera de esta especificación |
| Barra de acciones | QFrame | QHBoxLayout | Cinco QToolButton y cuatro QFrame VLine | Acceso permanente a las acciones principales |
| Botón de acción | QToolButton con ToolButtonTextUnderIcon | n/a | n/a | Acción individual con icono y doble etiqueta |
| Panel de control | QFrame | QVBoxLayout | ControlSegmentado, ContenidoPanel, PieControl | Configuración y visualización del mando |
| Control segmentado | QFrame con QButtonGroup exclusivo | QHBoxLayout | Dos QPushButton checkable | Conmuta entre Configuración y Visualización del control |
| Cuerpo desplazable | QScrollArea con QStackedWidget | n/a | VistaConfiguracion, VistaVisualizacionControl | Permite desplazamiento cuando el contenido excede la altura |
| Selector de control | QComboBox | n/a | n/a | Selección del dispositivo activo |
| Botón refrescar | QToolButton | n/a | n/a | Reenumera dispositivos |
| Indicador de conexión | QWidget | QHBoxLayout | QLabel punto, QLabel texto | Comunica el estado del dispositivo |
| Ilustración del mando | QSvgWidget o QLabel | n/a | n/a | Referencia visual del mando SNES |
| Lista de mapeo | QWidget | QVBoxLayout | Doce filas de mapeo | Asignación de entradas |
| Fila de mapeo | QWidget | QHBoxLayout | QLabel icono, QLabel nombre, QPushButton asignación | Una asignación de entrada lógica a entrada física |
| Botón restablecer | QPushButton | n/a | n/a | Revierte las asignaciones a sus valores iniciales |
| Diálogos de archivo | QFileDialog | n/a | n/a | Apertura de ROM y selección de estados |
| Confirmaciones y errores | QMessageBox o componente toast propio | n/a | n/a | Retroalimentación de guardado, carga y errores |

Justificaciones breves.

- Se usa `QMainWindow` por su soporte nativo de menús, restauración de geometría y modo de pantalla completa.
- El `QStackedWidget` del escenario hace determinística la conmutación de estados sin recrear widgets.
- El control segmentado se modela con `QButtonGroup` exclusivo sobre dos `QPushButton` checkable para reproducir el aspecto nativo de macOS y mantener consistencia en Windows.
- El `QScrollArea` garantiza el comportamiento responsive del panel por debajo del tamaño mínimo.

---

# Sistema visual

## Tipografía

Familia tipográfica del sistema con respaldo en Inter. En macOS se usa la fuente del sistema. En Windows se usa Segoe UI. Si ninguna está disponible, se usa Inter. Para datos técnicos como FPS o conteo de fotogramas se usa una variante monoespaciada del sistema.

| Rol | Tamaño | Peso | Interlineado | Uso |
|---|---|---|---|---|
| headline-lg | 24 px | 700 | 32 px | Títulos de vista y de juego |
| headline-md | 18 px | 600 | 24 px | Títulos secundarios |
| body-lg | 13 px | 400 | 18 px | Texto de cuerpo y controles, tamaño estándar |
| body-sm | 11 px | 400 | 16 px | Etiquetas secundarias |
| label-md | 12 px | 500 | 16 px | Etiquetas de control, interletrado 0,02em |
| label-caps | 10 px | 700 | 12 px | Encabezados de sección en mayúsculas, interletrado 0,05em |

## Espaciados

Rejilla base de 8 px. Todos los valores son múltiplos coherentes.

| Token | Valor | Uso |
|---|---|---|
| margin-window | 16 px | Márgenes del cuerpo |
| section-gap | 32 px | Separación entre regiones mayores del panel |
| stack-gap | 16 px | Separación entre escenario y barra de acciones |
| gutter-sidebar | 12 px | Separación interna del panel |
| padding-control | 8 px | Padding interno de controles |

## Iconografía

Estilo de línea coherente con iconografía sistémica. En macOS se prefieren símbolos del sistema. En Windows se usa un conjunto de iconos de línea equivalente. Tamaño recomendado de 20 px para iconos de control y de 24 px para iconos de la barra de acciones. Todos los iconos comparten grosor de trazo y métrica para mantener consistencia visual.

## Colores

### Tema claro

| Rol | Valor |
|---|---|
| Fondo principal | #F5F5F7 |
| Superficie de paneles | #FFFFFF |
| Superficie del escenario | #FAFAFA |
| Texto primario | #1D1D1F |
| Texto secundario | #6E6E73 |
| Borde y outline | #D2D2D7 |
| Borde sutil | #E5E5EA |
| Acento primario | #007AFF |
| Estado conectado | #34C759 |
| Estado reconectando | #FF9F0A |
| Estado error | #FF3B30 |
| Relleno de control | #FFFFFF |
| Hover de control | #F0F0F2 |

### Tema oscuro

| Rol | Valor |
|---|---|
| Fondo principal | #121317 |
| Superficie de paneles | #1E1F23 |
| Superficie del escenario | #0D0E12 |
| Superficie elevada | #292A2E |
| Superficie elevada máxima | #343539 |
| Texto primario | #E2E2E5 |
| Texto secundario | #C3C6CF |
| Borde y outline | #43474E |
| Outline fuerte | #8D9199 |
| Acento primario | #A2C9FF |
| Estado conectado | #34C759 |
| Estado reconectando | #FFB454 |
| Estado error | #FFB4AB |
| Relleno de control | #343539 |
| Hover de control | #38393D |

## Radios y profundidad

- Esquinas del escenario y del panel de control de 12 px.
- Botones e inputs con 6 px.
- Píldoras y puntos de estado con radio completo.
- La profundidad se logra con capas tonales y un borde de 1 px, sin sombras pronunciadas. Los modales usan la sombra estándar del sistema.

---

# Reglas de comportamiento

## Redimensionamiento y restricciones de layout

- El panel de control mantiene 320 px de ancho. El área principal absorbe toda variación.
- El escenario mantiene la relación de aspecto del modo de visualización activo con letterboxing.
- La barra de acciones conserva 88 px de alto y centra su grupo de botones.
- El escenario nunca queda con un ancho útil menor a 480 px. Por debajo del mínimo de ventana, el panel de control habilita desplazamiento vertical.

## Tamaños recomendados

- Tamaño mínimo de ventana de 1024 x 700 px.
- Tamaño inicial de ventana de 1360 x 860 px.

## Persistencia y restauración

- La configuración se almacena con `QSettings` con un dominio de organización y nombre de aplicación definidos.
- Se persisten las asignaciones de botones, el dispositivo seleccionado, el tema, el modo de visualización del escenario y la pestaña activa del panel.
- La geometría y el estado de la ventana se guardan con `saveGeometry` y se restauran con `restoreGeometry` al iniciar.
- Al salir de pantalla completa, la ventana recupera la geometría previa al modo.

## Cambios de resolución y HiDPI

- La aplicación habilita el escalado HiDPI de Qt y usa una política de redondeo del factor de escala que evite bordes borrosos.
- La superficie de video respeta el `devicePixelRatio` del monitor activo.
- Ante un cambio de pantalla o de resolución, el escenario recalcula el letterboxing y el escalado del modo activo sin perder la sesión.

---

# Consideraciones multiplataforma

## macOS

- Se usa el marco de ventana nativo con sus controles de tráfico. No se dibujan controles de ventana personalizados.
- Fuente del sistema. Atajos con la tecla Comando. Pantalla completa también disponible desde el control nativo verde.
- El control segmentado debe seguir la apariencia recesada nativa con pulgar deslizante.
- La translucidez de paneles es opcional. Si no se logra de forma fiable, se usa una superficie sólida del tema correspondiente.

## Windows

- Marco de ventana nativo con controles en la esquina superior derecha. El título permanece centrado.
- Fuente Segoe UI. Atajos con la tecla Control. Pantalla completa con F11.
- Superficies sólidas sin translucidez. El resto de tokens visuales se mantiene idéntico para preservar consistencia.

---

# Recomendaciones para implementación

- Construir primero el esqueleto de layout con `QMainWindow`, el cuerpo horizontal y las tres regiones del panel antes de poblar contenidos.
- Implementar el `QStackedWidget` del escenario con las cinco vistas vacías y validar la conmutación de estados antes de integrar la superficie de video.
- Definir todos los tokens de color, tipografía, espaciado y radio en una hoja de estilos central de la aplicación, con dos variantes seleccionables según el tema del sistema.
- Modelar la fila de mapeo como un widget reutilizable parametrizable por icono, nombre y asignación inicial, e instanciarlo doce veces a partir de la tabla de asignación.
- Centralizar el manejo de estados de sesión en un único controlador de vista que habilite o deshabilite las acciones dependientes de sesión de forma coherente.
- Implementar la confirmación de guardado y los errores con un componente de retroalimentación no bloqueante reutilizable.
- Verificar el comportamiento responsive en el tamaño mínimo de ventana y en pantalla completa antes de cerrar la fase de UI.
- Validar la apariencia en macOS y Windows con escalado HiDPI activo en ambas plataformas.
