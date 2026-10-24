# Generador de GeoJSON para mapas universitarios (GadirE)

Este proyecto **genera y actualiza** el archivo **GeoJSON** con los lugares georreferenciados del mapa interactivo de *GadirE* (PWA del CEUCA para la Universidad de Cádiz). Está formado por dos programas de Python y una herramienta auxiliar:

- **`adecuacion.py`**: revisa y clasifica los aportes del formulario de usuarios con un modelo de lenguaje local (Ollama) y genera un CSV intermedio validado.
- **`generador_map_data.py`**: infiere el campus y el edificio de cada lugar a partir de sus coordenadas (usando `campus.kml` y `edificios.kml`) y genera el GeoJSON final con identificadores únicos, **excluyendo los lugares con campus o edificio sin asignar (`None` o `"Desconocido"`)**.
- **`editor_kml.html`**: editor visual de los dos KML, sin instalación ni servidor; se abre en cualquier navegador moderno (ver `docs/kml_editor.md`).

## Contenido del repositorio

```
├── adecuacion.py             # Preprocesamiento y clasificación (moderación con Ollama)
├── generador_map_data.py     # Generación del GeoJSON
├── editor_kml.html            # Editor visual de campus.kml y edificios.kml (navegador)
├── campus.kml                 # Polígonos de los campus (inferencia geográfica)
├── edificios.kml              # Polígonos de los edificios (inferencia geográfica)
├── map_data_form.csv          # CSV de entrada (aportes del formulario de usuarios)
├── map_data.csv               # CSV intermedio (generado por adecuacion.py)
├── map_data.geojson           # GeoJSON final (generado por generador_map_data.py)
├── log.json                   # Estado incremental del generador
├── docs/
│   ├── gen_GeoJSON.md         # Documentación completa del generador
│   └── kml_editor.md          # Documentación del editor de KML
└── LICENSE
```

## Requisitos

- **Python** (probado en 3.9 y 3.13).
- Librerías: `pip install pandas ollama python-Levenshtein unidecode geopandas shapely`
- **Ollama** (solo para `adecuacion.py`): descargar el modelo con `ollama pull mistral:7b` (~4,4 GB) y tener el servicio en ejecución (`ollama serve`).

## Uso rápido

1. Colocar `map_data_form.csv` (los aportes del formulario) en la carpeta.
2. `python adecuacion.py` → genera/actualiza `map_data.csv`.
3. `python generador_map_data.py` → genera/actualiza `map_data.geojson` y `log.json`.
4. Copiar `map_data.geojson` a la carpeta `data` de *GadirE*.

El proceso es **idempotente**: reejecutar sin aportes aprobados nuevos no cambia nada. El funcionamiento detallado (entradas, salidas, códigos, incremental, despliegue, solución de problemas) está en `docs/gen_GeoJSON.md`.

**Regeneración completa** (empezar de cero; es el mecanismo normal de mantenimiento, no una emergencia): borrar `log.json` y `map_data.geojson` **juntos** y ejecutar de nuevo.

```bash
rm -f log.json map_data.geojson
python generador_map_data.py
```

**Nunca se borra uno sin el otro**: borrar solo el GeoJSON produce un resultado vacío (0 features), y borrar solo el `log.json` produce duplicados y features fantasma. Si los archivos de estado pertenecen a root (p. ej. porque los crea un cron), usar `sudo rm -f`.

## Polígonos de campus y edificios

Los KML definen los límites que el generador usa para inferir el campus y el edificio de cada lugar; el `<name>` de cada polígono debe coincidir **exactamente** con los nombres de `campus_codes`/`edificio_codes` en `generador_map_data.py`. Para crearlos o editarlos, usar **`editor_kml.html`** (documentado en `docs/kml_editor.md`), que exporta los archivos directamente en el formato exacto que lee el generador. Como alternativa, [Google My Maps](https://www.google.com/maps/about/mymaps/) permite dibujar los polígonos y exportarlos como KML.

## Documentación

- **`docs/gen_GeoJSON.md`**: funcionamiento completo del generador — especificaciones de entrada y salida, códigos e `idnum`, procesamiento incremental, regeneración, casos de uso, despliegue en producción y solución de problemas.
- **`docs/kml_editor.md`**: uso del editor visual de KML — dibujo, validación, compatibilidad con el generador y flujo de trabajo recomendado.

## Licencia

Ver el archivo `LICENSE`.