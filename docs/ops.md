# Guía de operación (scripts, cron y servidor)

Los scripts de operación manejan el backend de producción sin tocar el pipeline a mano. Todos comparten `registro.py`: rutas y URLs, log exhaustivo, descarga atómica con validación, publicación con permisos y bloqueo contra ejecuciones solapadas.

## Los scripts

| Script | Qué hace | Cuándo |
|---|---|---|
| `update.py` | Actualización **incremental** completa: descarga el CSV del formulario (atómica y validada) → `adecuacion.py` → `generador_map_data.py` → publica `map_data.geojson` en la web. | Mantenimiento diario (lo que hace el cron). |
| `reset.py` | **Reset** (regeneración completa): respalda y borra `log.json` + `map_data.geojson` **juntos** y reconstruye TODO. Pide confirmar escribiendo exactamente `GadirE`. | A propósito: purga fantasmas, recupera filas, repara estado. |
| `calendario.py` | Descarga el ICS de la Presidencia del CEUCA (atómica, validada) y lo publica en la web. | Diario (cron). |
| `cron.py` | Punto de entrada del cron: `python3 cron.py mapa` \| `calendario` \| `todo`. | Solo lo llama el crontab. |
| `estado.py` | Radiografía de solo lectura: archivos, últimas ejecuciones, procesados, fusiones, avisos, conflictos pendientes, veredictos del CSV, comprobaciones de idnum. | Siempre que se quiera mirar cómo está todo. |

Notas de uso:

- **`map_data.csv` no se toca en un reset**: guarda los veredictos y aprobaciones manuales, y la moderación los reutiliza.
- **`map_data_form.csv` nunca se edita a mano**: cada `update.py`/`reset.py` lo re-descarga del formulario.
- Si el paso que falla es la descarga o la moderación, **no se publica nada**: la web conserva el último GeoJSON bueno.
- Los archivos publicados quedan con `chmod 644` y propietario `www-data` (si el script corre con sudo/root).

## El log: toda la información, siempre

Cada ejecución de `update.py`, `reset.py` o `calendario.py` registra **todo**, en tres destinos a la vez:

- **Consola** (inmediato, línea a línea: sirve para `nohup ... &` + `tail -f`).
- **`logs/<script>_<fecha>.log`**: un archivo por ejecución, **nunca se borra**.
- **`logs/ultimo.log`**: siempre la última ejecución completa (se sobrescribe al empezar la siguiente).

Qué queda dentro: cada paso con su duración, la descarga con reintentos, **toda** la salida de `adecuacion.py` y `generador_map_data.py` (incluidas las respuestas crudas del LLM y las decisiones fila a fila: publicada, fusionada, excluida, no aprobada), los avisos y fusiones con sus motivos y, si algo falla, el **traceback completo**.

Además, `log.json` lleva el registro estructurado permanente: `procesados`, `id_counter`, `fusiones`, `avisos_duplicados` y, desde v14, **`ejecuciones`**: una entrada por pasada del generador con modo (`update`/`reset`/`manual`), duración, contadores por resultado, idnum asignados, fusiones/avisos de esa pasada y el resumen de la moderación. El formato es compatible hacia atrás: los logs anteriores simplemente no traen las claves nuevas.

## El cron del servidor

El crontab de root llama **solo a `cron.py`** (nunca a los demás), con el python3 del venv directamente (así no hace falta activar nada):

```cron
0 4 * * 1-5   /home/alfco28/generador_geojson_gadire/venv/bin/python3 /home/alfco28/generador_geojson_gadire/cron.py mapa
30 4 * * *   /home/alfco28/generador_geojson_gadire/venv/bin/python3 /home/alfco28/generador_geojson_gadire/cron.py calendario
```

Para cambiar el crontab: `sudo crontab -e` y sustituir las dos líneas antiguas (`actualizar_mapa.sh` y `actualiza_calendario_pre_ceuca.sh`) por las de arriba. Verificar con `sudo crontab -l`. Comprobar la zona horaria del servidor antes de fiarse de las horas.

Instalación de una nueva versión del backend en el servidor (los `.py` del repo van al clon de `~/generador_geojson_gadire`):

```bash
scp *.py alfco28@<servidor>:~/generador_geojson_gadire/
ssh alfco28@<servidor> 'cd generador_geojson_gadire && python3 estado.py'
```

(Si el clon tiene archivos de estado modificados respecto al repo, `git pull` puede negarse: en producción lo simple es copiar los `.py` directamente, como arriba.)

## Reset: cuándo y cómo

```bash
sudo python3 reset.py
```

- Pide escribir **exactamente** `GadirE` (con las mayúsculas) antes de tocar nada.
- Respalda `log.json` y `map_data.geojson` en `backups/<fecha>/` **y los borra juntos**; si algo falla a mitad, restaura lo movido (nunca queda un estado a medias).
- Después ejecuta el pipeline completo en modo `reset` (consta en `log.json`).

**Hacer reset** cuando: se sospechan duplicados o fantasmas, el `log.json` presenta contadores extraños o el formato antiguo, tras editar KML o filas a mano, o como saneamiento periódico. No es rutina: lo normal es `update.py`.

El generador tiene además **guardas de coherencia**: si se borra un archivo de estado sin el otro, aborta con un mensaje claro en lugar de publicar un mapa vacío (log sin geojson) o duplicar todo (geojson sin log). La salida a esa situación es siempre el reset.

## Interacción con el despliegue del frontend

El deploy del frontend **pisa `/var/www/Gadire/data/`**, incluido `map_data.geojson` y el ICS. Por eso:

1. Cada release del frontend debería llevar el `map_data.geojson` actualizado desde producción.
2. Tras cada deploy del frontend, **relanzar la actualización** (`python3 update.py` y `python3 calendario.py`, o esperar al cron) para no dejar en la web datos más viejos que los del servidor.
3. Tras cambiar el GeoJSON, recordar el **bump de la caché del service worker** (`CACHE_NAME` en `sw.js`) del frontend.

La fuente canónica del dato es la producción:

```bash
curl -o data/map_data.geojson https://gadire.alfeva.net/data/map_data.geojson
```

## Solución de problemas de operación

| Problema | Causa | Solución |
|---|---|---|
| `Ya hay otra ejecución en marcha` | Dos updates solapados (cron + manual). | Esperar a que acabe la otra; el bloqueo se libera solo. |
| Un script no puede publicar/chmod en `/var/www` | Ejecutado sin sudo con archivos de root. | Ejecutar con `sudo` (o dejarlo al cron, que corre como root). |
| GeoJSON vacío en la web | (Ya no puede pasar por borrado parcial: el generador aborta antes de publicar.) Si ocurriera: estado a medias. | `sudo python3 reset.py` y revisar `logs/ultimo.log`. |
| El cron no actualiza | Líneas antiguas del crontab, venv movido, o descarga del CSV caída (3 reintentos). | `sudo crontab -l`, `logs/ultimo.log`, probar `python3 cron.py mapa` a mano. |
| Dónde está lo que pasó anoche | — | `ls -t logs/ | head`, `cat logs/ultimo.log`, `python3 estado.py`. |
