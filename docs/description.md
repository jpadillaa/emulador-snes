# Arquitectura del Frontend para Emulador de SNES en macOS

## 1. Visión general

El proyecto consiste en el diseño y desarrollo de una aplicación de escritorio nativa para macOS construida en Python. La aplicación actúa como una capa de presentación y gestión sobre un núcleo de emulación de Super Nintendo de terceros. El diseño prioriza la separación estricta entre la lógica de interfaz de usuario y el procesamiento de la emulación. Se busca alta modularidad, bajo acoplamiento y una estructura que permita reemplazar el núcleo de emulación si fuera necesario sin reescribir la aplicación principal.

## 2. Objetivos

### Requerimientos funcionales

- Analizar directorios locales para identificar y listar archivos ROM válidos.
- Presentar una biblioteca interactiva con los roms.
- Proveer una interfaz gráfica para la configuración de controles físicos y teclado.
- Gestionar la persistencia de estados de guardado y partidas.
- Configurar parámetros de salida de video y audio.
- Interpretar eventos de entrada y enviarlos al núcleo de emulación.
- Capturar los búferes de audio y video del núcleo para su renderizado en pantalla.
    
### Requerimientos no funcionales
- Mantenibilidad a través de la segregación de interfaces y el patrón adaptador.
- Modularidad estructurada en componentes independientes con responsabilidades únicas.
- Rendimiento óptimo garantizando que la capa de Python no introduzca latencia perceptible en la ejecución del núcleo escrito en C o C++.
- Experiencia de usuario alineada con los estándares de diseño de macOS integrando aceleración por hardware y menús nativos.
    
## 3. Arquitectura

El sistema utiliza una arquitectura basada en capas y el patrón Modelo Vista Controlador. La aplicación se divide en la Capa de Presentación, la Capa de Dominio y la Capa de Infraestructura. El núcleo de emulación se sitúa fuera del dominio de la aplicación interactuando exclusivamente a través de un adaptador.

```
graph TD
    UI[Capa de Presentación / Interfaz Gráfica]
    Controlador[Controlador Principal de la Aplicación]
    Lib[Gestor de Biblioteca]
    Config[Gestor de Configuración]
    Input[Gestor de Entrada y Controles]
    Bridge[Adaptador del Núcleo]
    Core[Núcleo de Emulación Externo]
    DB[(Base de Datos Local)]

    UI --> Controlador
    Controlador --> Lib
    Controlador --> Config
    Controlador --> Input
    Controlador --> Bridge
    Lib --> DB
    Config --> DB
    Bridge --> Core
    Input --> Bridge
```

## 4. Flujo de funcionamiento
- El usuario interactúa con la interfaz y selecciona un juego.
- La Capa de Presentación notifica al Controlador Principal la solicitud de ejecución.
- El Controlador Principal instruye al Adaptador del Núcleo para inicializar el componente de emulación con la ruta del archivo ROM seleccionado.
- La interfaz transiciona al modo de visualización de juego.
- El Gestor de Entrada captura los eventos del teclado o controles Bluetooth y los traduce al formato requerido por el Adaptador del Núcleo.
- El Adaptador del Núcleo recupera los fotogramas y muestras de audio generados por el núcleo externo y los transfiere a la vista correspondiente para su renderizado continuo.
- El usuario interrumpe la ejecución mediante un comando. El Controlador Principal ordena al Adaptador del Núcleo guardar el estado y detener el procesamiento.
    
## 5. Módulos principales

### Capa de Presentación
- **Propósito** Renderizar la interfaz gráfica e interpretar las interacciones del usuario.
- **Responsabilidades** Dibujar ventanas, menús, cuadrícula de juegos y la superficie de renderizado de video.
- **Entradas** Acciones del usuario mediante ratón y teclado. Búferes de video provenientes del Adaptador del Núcleo.
- **Salidas** Eventos de interfaz dirigidos al Controlador Principal.
- **Dependencias** Framework de interfaz gráfica de Python.
    
### Gestor de Biblioteca
- **Propósito** Administrar el inventario de juegos del usuario.
- **Responsabilidades** Escanear el sistema de archivos, calcular firmas digitales de las ROMs, obtener metadatos y almacenar la información de las partidas.
- **Entradas** Rutas de directorios locales proporcionadas por el usuario.
- **Salidas** Listas estructuradas de juegos y sus metadatos.
- **Dependencias** Sistema de archivos y base de datos local.
    
### Gestor de Configuración
- **Propósito** Centralizar las preferencias de la aplicación.
- **Responsabilidades** Leer y escribir configuraciones de video, audio, rutas por defecto y atajos de teclado.
- **Entradas** Modificaciones realizadas por el usuario en la interfaz.
- **Salidas** Estructuras de datos con los parámetros activos.
- **Dependencias** Sistema de archivos.

### Gestor de Entrada
- **Propósito** Unificar el manejo de periféricos.
- **Responsabilidades** Detectar dispositivos Bluetooth, capturar pulsaciones de teclado y mapear estos eventos físicos a botones virtuales de SNES.
- **Entradas** Eventos de hardware del sistema operativo.
- **Salidas** Estados de los botones virtuales de la consola.
- **Dependencias** APIs nativas de entrada de macOS.

### Adaptador del Núcleo

- **Propósito** Aislar el código de Python de la implementación específica del núcleo de emulación.
- **Responsabilidades** Cargar la biblioteca externa, traducir los tipos de datos de Python a C y viceversa, enviar entradas y recibir salidas multimedia.
- **Entradas** Rutas de ROMs, estados de botones virtuales y comandos de control.
- **Salidas** Búferes de video y audio, datos crudos de estados de guardado.
- **Dependencias** Núcleo de emulación externo y biblioteca de integración de bajo nivel de Python.
    
## 6. Funcionalidades de la interfaz

### Biblioteca de juegos

Utiliza un modelo de datos asíncrono para mantener la interfaz receptiva. Implementa una vista de cuadrícula renderizada a partir de la base de datos local. Las imágenes de portada se almacenan en caché local y se cargan bajo demanda.

### Configuración de controles

Presenta una vista modal que asocia un controlador físico detectado a un mapa de memoria estructurado. Utiliza un patrón de escucha activa para asignar botones esperando la siguiente pulsación del usuario y guardando la relación en el Gestor de Configuración.

### Guardado y carga de partidas

Se integra en la barra de menú nativa de macOS y en atajos de teclado globales de la aplicación. Al activarse invoca una función de bloqueo temporal en el Adaptador del Núcleo, extrae la memoria serializada, la comprime y la escribe en el disco asociada a una captura de pantalla del instante actual.

### Configuración de video

Ofrece selectores para filtros de escalado y relación de aspecto. Estos valores se transmiten a la superficie de renderizado de la Capa de Presentación la cual aplica las transformaciones espaciales mediante aceleración por hardware antes de pintar el búfer recibido del núcleo.

### Configuración de audio

Expone un control de volumen general y opciones de latencia de búfer. Los ajustes modifican el comportamiento del flujo de audio administrado por la herramienta de reproducción de la aplicación ajustando el tamaño del bloque leído desde el Adaptador del Núcleo.

### Pantalla completa

Delega completamente en la API de gestión de ventanas nativa de macOS para asegurar la compatibilidad con espacios de trabajo y animaciones del sistema operativo.

### Soporte para controles Bluetooth

Implementa un proceso en segundo plano que monitorea la conexión y desconexión de dispositivos mediante los subsistemas del sistema operativo. Al detectar un dispositivo lo registra en el Gestor de Entrada asignando un perfil predeterminado si existe.
## 7. Tecnologías recomendadas

### Interfaz gráfica

**PySide6** Justificación técnica para su uso radica en su excelente integración con los componentes nativos de macOS. Permite el uso de aceleración por hardware a través de Metal para el renderizado eficiente de los búferes de video del emulador. Facilita la creación de una arquitectura asíncrona mediante señales y ranuras.

### Configuración

**JSON** Justificación técnica para su uso se basa en la simplicidad para serializar diccionarios de Python. Permite la edición manual por parte del usuario si el entorno gráfico falla y es ligero para lectura secuencial al inicio de la aplicación.

### Integración con el núcleo de emulación

**ctypes o cffi** Justificación técnica depende directamente de la naturaleza del núcleo externo. Si el núcleo se compila como una biblioteca compartida dinámica, estas herramientas permiten enlazar las funciones expuestas en memoria transcodificando punteros y búferes sin necesidad de comunicación entre procesos. Si el núcleo es un ejecutable independiente, la arquitectura deberá ajustarse para utilizar `subprocess` y tuberías de comunicación.

