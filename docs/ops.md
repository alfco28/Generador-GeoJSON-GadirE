# Guía de operación (scripts, cron y servidor)

Los puntos de entrada de `commands/` manejan el backend de producción sin tocar el pipeline a mano. Todos comparten `commands/scripts/pipeline.py`: rutas y URLs, log exhaustivo, descarga atómica con validación, publicación con permisos y bloqueo contra ejecuciones solapadas.

## Los puntos de entrada

| Script | Qué hace | Cuándo |
|---|---|---|
| `commands/update.py` | Actualización **incremental** completa: descarga el CSV del formulario (atómica y validada) → `moderation.py` → `generate_geojson.py` → publica `map_data.geojson` en la web. | Mantenimiento diario (lo que hace el cron). |
| `commands/reset.py` | **Reset** (regeneración completa): respalda y borra `log.json` + `map_data.geojson` **juntos** y reconstruye TODO. Pide confirmar escribiendo exactamente `GadirE`. | A propósito: purga fantasmas, recupera filas, repara estado. |
| `commands/ics.py` | Descarga el ICS de la Presidencia del CEUCA (atómica, validada) y lo publica en la web. | Diario (cron). |
| `commands/cron.py` | Punto de entrada del cron: `python3 cron.py mapa` \| `calendario` \| `todo`. | Solo lo llama el crontab. |
| `commands/status.py` | Radiografía de solo lectura: archivos, últimas ejecuciones, procesados, fusiones, avisos, conflictos pendientes, veredictos del CSV, comprobaciones de idnum. | Siempre que se quiera mirar cómo está todo. |
| `commands/review.py` | Revisión manual: entradas pendientes ("Revisar manualmente") y gestión de los puntos publicados (inspección, corrección, retirada). Ver `docs/review.md`. | Cuando haya entradas que el LLM no supo decidir, o que corregir o retirar algo ya publicado. |

`commands/scripts/pipeline.py` es el motor interno compartido: **nunca se ejecuta a mano**; lo importan los puntos de entrada.

Notas de uso:

- **`map_data.csv` no se toca en un reset**: guarda los veredictos y aprobaciones manuales, y la moderación los reutiliza.
- **`map_data_form.csv` nunca se edita a mano**: cada `update.py`/`reset.py` lo re-descarga del formulario.
- Si el paso que falla es la descarga o la moderación, **no se publica nada**: la web conserva el último GeoJSON bueno.
- Los archivos publicados quedan con `chmod 644` y propietario `www-data` (si el script corre con sudo/root).

## El log: toda la información, siempre

Cada ejecución de `update.py`, `reset.py` o `ics.py` registra **todo**, en tres destinos a la vez:

- **Consola** (inmediato, línea a línea: sirve para `nohup ... &` + `tail -f`).
- **`gen_geojson/logs/<script>_<fecha>.log`**: un archivo por ejecución, **nunca se borra**.
- **`gen_geojson/logs/ultimo.log`**: siempre la última ejecución completa (se sobrescribe al empezar la siguiente).

Qué queda dentro: cada paso con su duración, la descarga con reintentos, **toda** la salida de `moderation.py` y `generate_geojson.py` (incluidas las respuestas crudas del LLM y las decisiones fila a fila: publicada, fusionada, excluida, no aprobada), los avisos y fusiones con sus motivos y, si algo falla, el **traceback completo**.

Además, `log.json` lleva el registro estructurado permanente: `procesados`, `id_counter`, `fusiones`, `avisos_duplicados` y **`ejecuciones`**: una entrada por pasada del generador con modo (`update`/`reset`/`manual`), duración, contadores por resultado, idnum asignados, fusiones/avisos de esa pasada y el resumen de la moderación. El formato es compatible hacia atrás: los logs anteriores simplemente no traen las claves nuevas.

## Instalación genérica

En el servidor, la instalación de referencia es un clon del repositorio más un entorno virtual con las dependencias:

```bash
git clone https://github.com/alfco28/Generador-GeoJSON-GadirE.git
cd Generador-GeoJSON-GadirE
python3 -m venv venv
venv/bin/pip install pandas ollama python-Levenshtein unidecode geopandas shapely
```

Para las rutas por defecto, `pipeline.py` espera esta disposición (todas sobrescribibles con las variables de entorno `GADIRE_RUTA_PROYECTO`, `GADIRE_RUTA_WEB`, `GADIRE_RUTA_LOGS`, `GADIRE_URL_CSV` y `GADIRE_URL_ICS`):

- **Proyecto**: `gen_geojson/` dentro del clon (los programas del pipeline, los KML y todos los archivos de estado).
- **Web**: `/var/www/Gadire/data` (¡`Gadire` con mayúscula! Linux distingue mayúsculas y minúsculas).
- **Logs**: `gen_geojson/logs/` dentro del proyecto.

**Ollama** solo lo necesita `moderation.py`: instalar el servicio, descargar el modelo (`ollama pull mistral:7b`) y dejarlo arrancado.

Actualización de una instalación existente: `git pull --ff-only` en el clon (los archivos de estado que el clon tenga modificados respecto al repo se pueden guardar con `git stash` antes del pull y recuperarse después; ver `docs/review.md` para el caso general). Si el crontab apunta a `cron.py`, **no hay que tocarlo salvo que cambien las rutas del clon o del venv**.

## El cron

El crontab llama **solo a `commands/cron.py`** (nunca a los demás), con el python3 del venv directamente (así no hace falta activar nada), con rutas absolutas al clon:

```cron
0 4 * * 1-5   /ruta/al/clon/venv/bin/python3 /ruta/al/clon/commands/cron.py mapa
30 4 * * *    /ruta/al/clon/venv/bin/python3 /ruta/al/clon/commands/cron.py calendario
```

Para cambiar el crontab: `sudo crontab -e` y dejar las dos líneas apuntando a `commands/cron.py`. Verificar con `sudo crontab -l`. Comprobar la zona horaria del servidor antes de fiarse de las horas (el cron dispara en la hora local del servidor).

## Reset: cuándo y cómo

```bash
sudo python3 commands/reset.py
```

- Pide escribir **exactamente** `GadirE` (con las mayúsculas) antes de tocar nada.
- Respalda `log.json` y `map_data.geojson` en `gen_geojson/backups/<fecha>/` **y los borra juntos**; si algo falla a mitad, restaura lo movido (nunca queda un estado a medias).
- Después ejecuta el pipeline completo en modo `reset` (consta en `log.json`).

**Hacer reset** cuando: se sospechan duplicados o fantasmas, el `log.json` presenta contadores extraños o el formato antiguo, tras editar KML, o como saneamiento periódico. No es rutina: lo normal es `update.py`.

El generador tiene además **guardas de coherencia**: si se borra un archivo de estado sin el otro, aborta con un mensaje claro en lugar de publicar un mapa vacío (log sin geojson) o duplicar todo (geojson sin log). La salida a esa situación es siempre el reset.

## Interacción con el despliegue del frontend

El deploy del frontend **pisa la carpeta de datos servida** (incluido `map_data.geojson` y el ICS). Por eso:

1. Cada release del frontend debería llevar el `map_data.geojson` actualizado desde producción.
2. Tras cada deploy del frontend, **relanzar la actualización** (`python3 commands/update.py` y `python3 commands/ics.py`, o esperar al cron) para no dejar en la web datos más viejos que los del servidor.
3. Tras cambiar el GeoJSON, recordar el **bump de la caché del service worker** (`CACHE_NAME` en `sw.js`) del frontend si procede según su estrategia de caché.

La fuente canónica del dato es la producción.

## Solución de problemas de operación

| Problema | Causa | Solución |
|---|---|---|
| `Ya hay otra ejecución en marcha` | Dos updates solapados (cron + manual). | Esperar a que acabe la otra; el bloqueo se libera solo. |
| Un script no puede publicar/chmod en la carpeta web | Ejecutado sin sudo con archivos de root. | Ejecutar con `sudo` (o dejarlo al cron, que corre como root). |
| GeoJSON vacío en la web | (Ya no puede pasar por borrado parcial: el generador aborta antes de publicar.) Si ocurriera: estado a medias. | `sudo python3 commands/reset.py` y revisar `gen_geojson/logs/ultimo.log`. |
| El cron no actualiza | Líneas antiguas del crontab, venv movido, o descarga del CSV caída (3 reintentos). | `sudo crontab -l`, `gen_geojson/logs/ultimo.log`, probar `python3 commands/cron.py mapa` a mano. |
| Dónde está lo que pasó anoche | — | `ls -t gen_geojson/logs/ | head`, `cat gen_geojson/logs/ultimo.log`, `python3 commands/status.py`. |
| Un punto publicado está mal (nombre, tipo...) o no debería estar | Aporte aprobado con datos erróneos. | `python3 commands/review.py point <idnum> ...` (ver `docs/review.md`); si se retira, lanzar `update.py` para publicar el cambio. |
