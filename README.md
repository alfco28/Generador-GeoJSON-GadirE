# Generador del GeoJSON para GadirE

Este proyecto **genera y actualiza** el archivo **GeoJSON** con los lugares georreferenciados del mapa interactivo de *GadirE* (PWA del CEUCA para la Universidad de Cádiz). Está formado por los dos programas del pipeline, un módulo común, una herramienta auxiliar y los scripts de operación:

- **`adecuacion.py`**: revisa y clasifica los aportes del formulario de usuarios con un modelo de lenguaje local (Ollama) y genera un CSV intermedio validado.
- **`generador_map_data.py`**: infiere el campus y el edificio de cada lugar a partir de sus coordenadas (usando `campus.kml` y `edificios.kml`) y genera el GeoJSON final con identificadores únicos, **excluyendo los lugares con campus o edificio sin asignar (`None` o `"Desconocido"`)**.
- **`dedup.py`**: detección de reportes duplicados de un mismo lugar con **fusión aditiva** (si un punto ya existe, se añade la información nueva a la feature existente; nunca se crea una duplicada). Lo comparten los dos programas (ver `docs/dedup.md`).
- **`registro.py`**: módulo común de los scripts de operación: rutas y URLs, registro (log) exhaustivo de cada ejecución, descarga atómica con validación y publicación en la web.
- **`update.py`**: actualización **incremental** del mapa (lo mismo que hace el cron): descarga el CSV del formulario, modera, genera y publica.
- **`reset.py`**: **reset** (nombre definitivo de la regeneración completa): borra el estado y reconstruye TODO; pide confirmación escribiendo exactamente `GadirE`.
- **`calendario.py`**: descarga y publica, de forma atómica, el ICS del calendario de la Presidencia del CEUCA.
- **`cron.py`**: punto de entrada único del cron: `cron.py mapa`, `cron.py calendario` o `cron.py todo`.
- **`estado.py`**: radiografía del proyecto sin ejecutar nada (conteos, últimas ejecuciones, conflictos, comprobaciones).
- **`kml_editor/`**: editor visual de los dos KML, sin instalación ni servidor; se abre en cualquier navegador moderno (ver `docs/kml_editor.md`).

## Contenido del repositorio

```
├── adecuacion.py             # Preprocesamiento y clasificación (moderación con Ollama)
├── generador_map_data.py     # Generación del GeoJSON (incremental por Timestamp)
├── dedup.py                  # Deduplicación con fusión aditiva (compartido)
├── registro.py               # Módulo común: logging, rutas, descarga atómica, publicación
├── update.py                 # Actualización incremental (lo que hace el cron)
├── reset.py                  # Reset: reconstrucción completa (confirmación "GadirE")
├── calendario.py             # Publicación atómica del ICS de la Presidencia
├── cron.py                   # Punto de entrada del cron (mapa | calendario | todo)
├── estado.py                 # Estado del proyecto de un vistazo (sólo lectura)
├── campus.kml                 # Polígonos de los campus (inferencia geográfica)
├── edificios.kml              # Polígonos de los edificios (inferencia geográfica)
├── kml_editor/                # Editor visual de los KML (navegador)
├── map_data_form.csv          # CSV de entrada (aportes del formulario de usuarios)
├── map_data.csv               # CSV intermedio (generado por adecuacion.py)
├── map_data.geojson           # GeoJSON final (generado por generador_map_data.py)
├── log.json                   # Estado incremental y registro de ejecuciones
├── docs/
│   ├── gen_GeoJSON.md         # Documentación completa del generador
│   ├── dedup.md               # Documentación de la deduplicación con fusión aditiva
│   ├── ops.md                 # Guía de operación: scripts, cron, servidor, logs
│   └── kml_editor.md          # Documentación del editor de KML
├── logs/                      # Un log por ejecución + logs/ultimo.log (ignorado por git)
├── backups/                   # Respaldos automáticos de los resets (ignorado por git)
└── LICENSE
```

## Requisitos

- **Python** (probado en 3.9 y 3.13).
- Librerías: `pip install pandas ollama python-Levenshtein unidecode geopandas shapely`
- **Ollama** (solo para `adecuacion.py`): descargar el modelo con `ollama pull mistral:7b` (~4,4 GB) y tener el servicio en ejecución (`ollama serve`).

## Uso rápido

El mantenimiento diario son los **scripts de operación** (ver `docs/ops.md` para el servidor y el cron):

```bash
python3 update.py      # actualización incremental (lo que hace el cron cada noche)
python3 estado.py      # ver cómo está todo sin ejecutar nada
sudo python3 reset.py  # reset completo (pide confirmar escribiendo "GadirE")
```

Cada ejecución deja un **log completo** en `logs/` (uno por ejecución, más `logs/ultimo.log` con la última): descarga, decisiones de la moderación con las respuestas crudas del modelo, decisiones del generador fila a fila, fusiones, avisos y, si algo falla, el traceback completo.

El pipeline también se puede ejecutar a mano, paso a paso:

1. Colocar `map_data_form.csv` (los aportes del formulario) en la carpeta.
2. `python3 adecuacion.py` → genera/actualiza `map_data.csv`.
3. `python3 generador_map_data.py` → genera/actualiza `map_data.geojson` y `log.json`.
4. Copiar `map_data.geojson` a la carpeta `data` de *GadirE*.

El proceso es **idempotente**: reejecutar sin aportes aprobados nuevos no cambia nada.

**Reset** (empezar de cero; es el mecanismo normal de mantenimiento, no una emergencia): usar `reset.py`, que respalda y borra `log.json` y `map_data.geojson` **juntos** y reconstruye todo. Nunca se borra uno sin el otro: el generador detecta el estado incoherente y aborta pidiendo el reset, en lugar de publicar un mapa vacío o duplicar todo.

**Nunca se edita `map_data_form.csv`**: lo reescribe la descarga del formulario en cada actualización. Las correcciones manuales (veredictos, tipos) van en `map_data.csv`, que la moderación reutiliza.

## Deduplicación (fusión aditiva)

Si un aporte repite un punto que ya está publicado (o ya reportado en el mismo lote), **no se crea una feature nueva**: la información nueva se **añade** a la existente (descripción ampliada, enlace rellenado, alias registrado en `log.json`), sin suprimir ni sustituir nada. La detección combina nombre normalizado, planta y distancia entre coordenadas, con el modelo de lenguaje solo para los casos ambiguos. El diseño completo está en `docs/dedup.md`.

## Polígonos de campus y edificios

Los KML definen los límites que el generador usa para inferir el campus y el edificio de cada lugar; el `<name>` de cada polígono debe coincidir **exactamente** con los nombres de `campus_codes`/`edificio_codes` en `generador_map_data.py`. Para crearlos o editarlos, usar el **editor de KML** de `kml_editor/` (documentado en `docs/kml_editor.md`), que exporta los archivos directamente en el formato exacto que lee el generador. Como alternativa, [Google My Maps](https://www.google.com/maps/about/mymaps/) permite dibujar los polígonos y exportarlos como KML.

## Documentación

- **`docs/gen_GeoJSON.md`**: funcionamiento completo del generador — especificaciones de entrada y salida, códigos e `idnum`, procesamiento incremental, reset, casos de uso y solución de problemas.
- **`docs/dedup.md`**: la deduplicación con fusión aditiva — reglas de detección, política de fusión campo a campo, conflictos y auditoría en `log.json`.
- **`docs/ops.md`**: guía de operación — scripts, logging, cron del servidor, despliegue y interacción con el frontend.
- **`docs/kml_editor.md`**: uso del editor visual de KML — dibujo, validación, compatibilidad con el generador y flujo de trabajo recomendado.

## Licencia

Ver el archivo `LICENSE`.
