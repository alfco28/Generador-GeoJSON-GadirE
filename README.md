# Generador del GeoJSON para GadirE

Este proyecto **genera y actualiza** el archivo **GeoJSON** con los lugares georreferenciados del mapa interactivo de *GadirE* (PWA del CEUCA para la Universidad de Cádiz). Está formado por los dos programas del pipeline, un módulo común, una herramienta de revisión manual y los scripts de operación:

- **`gen_geojson/moderation.py`**: revisa y clasifica los aportes del formulario de usuarios con un modelo de lenguaje local (Ollama) y genera un CSV intermedio validado.
- **`gen_geojson/generate_geojson.py`**: infiere el campus y el edificio de cada lugar a partir de sus coordenadas (usando `campus.kml` y `edificios.kml`) y genera el GeoJSON final con identificadores únicos, **excluyendo los lugares con campus o edificio sin asignar (`None` o `"Desconocido"`)**.
- **`gen_geojson/dedup.py`**: detección de reportes duplicados de un mismo lugar con **fusión aditiva** (si un punto ya existe, se añade la información nueva a la feature existente; nunca se crea una duplicada). Lo comparten los dos programas (ver `docs/dedup.md`).
- **`commands/scripts/pipeline.py`**: módulo común de los puntos de entrada de operación: rutas y URLs, registro (log) exhaustivo de cada ejecución, descarga atómica con validación y publicación en la web. No se ejecuta a mano.
- **`commands/update.py`**: actualización **incremental** del mapa (lo mismo que hace el cron): descarga el CSV del formulario, modera, genera y publica.
- **`commands/reset.py`**: **reset** (nombre definitivo de la regeneración completa): borra el estado y reconstruye TODO; pide confirmación escribiendo exactamente `GadirE`.
- **`commands/ics.py`**: descarga y publica, de forma atómica, el ICS del calendario de la Presidencia del CEUCA. (Se llama `ics.py`, y no `calendar.py`, porque `calendar` es un módulo de la biblioteca estándar de Python que pandas y otras librerías importan: un archivo con ese nombre en la misma carpeta lo taparía.)
- **`commands/cron.py`**: punto de entrada único del cron: `cron.py mapa`, `cron.py calendario` o `cron.py todo`.
- **`commands/status.py`**: radiografía del proyecto sin ejecutar nada (conteos, últimas ejecuciones, conflictos, comprobaciones).
- **`commands/review.py`**: revisión manual: decide las entradas pendientes ("Revisar manualmente") e inspecciona, corrige o retira los puntos ya publicados (ver `docs/review.md`).
- **`kml_editor/`**: editor visual de los dos KML, sin instalación ni servidor; se abre en cualquier navegador moderno (ver `docs/kml_editor.md`).

## Contenido del repositorio

```
├── commands/                     # Puntos de entrada (se ejecutan a mano o el cron)
│   ├── update.py                 # Actualización incremental (lo que hace el cron)
│   ├── reset.py                  # Reset: reconstrucción completa (confirmación "GadirE")
│   ├── ics.py                    # Publicación atómica del ICS de la Presidencia
│   ├── cron.py                   # Punto de entrada del cron (mapa | calendario | todo)
│   ├── status.py                 # Estado del proyecto de un vistazo (sólo lectura)
│   ├── review.py                 # Revisión manual: pendientes y puntos publicados
│   └── scripts/
│       └── pipeline.py           # Módulo común: logging, rutas, descarga, publicación
├── gen_geojson/                   # El pipeline y TODO su estado
│   ├── moderation.py             # Moderación con Ollama (antes adecuacion.py)
│   ├── generate_geojson.py       # Generación del GeoJSON (antes generador_map_data.py)
│   ├── dedup.py                  # Deduplicación con fusión aditiva (compartido)
│   ├── campus.kml                # Polígonos de los campus (inferencia geográfica)
│   ├── edificios.kml             # Polígonos de los edificios (inferencia geográfica)
│   ├── map_data_form.csv         # CSV de entrada (aportes del formulario)
│   ├── map_data.csv              # CSV intermedio (veredictos y tipos acumulados)
│   ├── map_data.geojson          # GeoJSON final (el que se publica)
│   └── log.json                  # Estado incremental y registro de ejecuciones
├── kml_editor/                   # Editor visual de los KML (navegador)
├── docs/                          # Documentación
└── LICENSE
```

`gen_geojson/logs/` (un log por ejecución, más `ultimo.log`) y `gen_geojson/backups/` (respaldos automáticos de resets y revisiones) se crean solos y están ignorados por git.

## Requisitos

- **Python** (probado en 3.9 y 3.13).
- Librerías: `pip install pandas ollama python-Levenshtein unidecode geopandas shapely`
- **Ollama** (solo para `moderation.py`): descargar el modelo con `ollama pull mistral:7b` (~4,4 GB) y tener el servicio en ejecución (`ollama serve`).

## Uso rápido

El mantenimiento diario son los **puntos de entrada de `commands/`** (ver `docs/ops.md` para el servidor y el cron):

```bash
python3 commands/update.py       # actualización incremental (lo que hace el cron cada noche)
python3 commands/status.py       # ver cómo está todo sin ejecutar nada
python3 commands/review.py list  # entradas pendientes de revisión manual
sudo python3 commands/reset.py   # reset completo (pide confirmar escribiendo "GadirE")
```

Cada ejecución deja un **log completo** en `gen_geojson/logs/` (uno por ejecución, más `ultimo.log` con la última): descarga, decisiones de la moderación con las respuestas crudas del modelo, decisiones del generador fila a fila, fusiones, avisos y, si algo falla, el traceback completo.

El pipeline también se puede ejecutar a mano, paso a paso, desde `gen_geojson/` (donde viven los KML y los archivos de estado):

1. Colocar `map_data_form.csv` (los aportes del formulario) en la carpeta.
2. `python3 moderation.py` → genera/actualiza `map_data.csv`.
3. `python3 generate_geojson.py` → genera/actualiza `map_data.geojson` y `log.json`.
4. Copiar `map_data.geojson` a la carpeta `data` de *GadirE*.

El proceso es **idempotente**: reejecutar sin aportes aprobados nuevos no cambia nada.

**Reset** (empezar de cero; es el mecanismo normal de mantenimiento, no una emergencia): usar `commands/reset.py`, que respalda y borra `log.json` y `map_data.geojson` **juntos** y reconstruye todo. Nunca se borra uno sin el otro: el generador detecta el estado incoherente y aborta pidiendo el reset, en lugar de publicar un mapa vacío o duplicar todo.

**Nunca se edita `map_data_form.csv`**: lo reescribe la descarga del formulario en cada actualización. Las correcciones manuales (veredictos, tipos) van en `map_data.csv` — con `commands/review.py` o a mano —, que la moderación reutiliza.

## Revisión manual

`commands/review.py` centraliza las dos decisiones humanas del pipeline (documentado en `docs/review.md`):

- **Entradas pendientes**: las que el LLM dejó en "Revisar manualmente". Se muestran con todos sus datos y se aceptan (`yes` → `Aprobado="Sí"`, reexaminando duplicados y tipo en el próximo update) o rechazan (`no` → `Aprobado="No"`).
- **Puntos ya publicados** (por `idnum`): inspección, corrección de cualquier campo (nombre, descripción, enlace, tipo, planta, coordenadas) y retirada del mapa con `retract`.

## Deduplicación (fusión aditiva)

Si un aporte repite un punto que ya está publicado (o ya reportado en el mismo lote), **no se crea una feature nueva**: la información nueva se **añade** a la existente (descripción ampliada, enlace rellenado, alias registrado en `log.json`), sin suprimir ni sustituir nada. La detección combina nombre normalizado, planta y distancia entre coordenadas, con el modelo de lenguaje solo para los casos ambiguos. El diseño completo está en `docs/dedup.md`.

## Polígonos de campus y edificios

Los KML definen los límites que el generador usa para inferir el campus y el edificio de cada lugar; el `<name>` de cada polígono debe coincidir **exactamente** con los nombres de `campus_codes`/`edificio_codes` en `generate_geojson.py`. Para crearlos o editarlos, usar el **editor de KML** de `kml_editor/` (documentado en `docs/kml_editor.md`), que exporta los archivos directamente en el formato exacto que lee el generador. Como alternativa, [Google My Maps](https://www.google.com/maps/about/mymaps/) permite dibujar los polígonos y exportarlos como KML.

## Documentación

- **`docs/gen_GeoJSON.md`**: funcionamiento completo del generador — especificaciones de entrada y salida, códigos e `idnum`, procesamiento incremental, reset, casos de uso y solución de problemas.
- **`docs/dedup.md`**: la deduplicación con fusión aditiva — reglas de detección, política de fusión campo a campo, conflictos y auditoría en `log.json`.
- **`docs/ops.md`**: guía de operación — scripts, logging, cron del servidor, despliegue e interacción con el frontend.
- **`docs/review.md`**: la revisión manual — entradas pendientes y gestión de los puntos publicados (inspección, corrección, retirada).
- **`docs/kml_editor.md`**: uso del editor visual de KML — dibujo, validación, compatibilidad con el generador y flujo de trabajo recomendado.

## Licencia

Ver el archivo `LICENSE`.
