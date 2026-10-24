# Revisión manual (`commands/review.py`)

`review.py` concentra las dos decisiones humanas del pipeline: qué hacer con las entradas que el modelo de lenguaje no supo decidir, y qué hacer con los puntos ya publicados que haya que corregir o retirar. Todo lo que escribe va a `map_data.csv`, `map_data.geojson` y `log.json` (nunca a `map_data_form.csv`, que la siguiente actualización re-descarga).

Las respuestas se escriben en inglés (`yes`/`no`), pero el CSV conserva los valores exactos en español que espera el pipeline: `Sí` / `No`.

## Entradas pendientes

El pipeline deja el veredicto **"Revisar manualmente"** cuando el LLM no se atreve a decidir. Esas filas se revisan así:

```bash
python3 review.py                # la pendiente MÁS ANTIGUA: mostrar + preguntar
python3 review.py list           # lista de todas las pendientes con su identificador
python3 review.py all            # repasarlas todas, una a una
python3 review.py "<timestamp>"   # muestra esa entrada y pregunta
python3 review.py "<timestamp>" yes   # responder directamente, sin mostrarla
python3 review.py "<timestamp>" no    # idem, rechazándola
```

- El **identificador** de cada pendiente es su **Timestamp del formulario** (único por envío; hay que escribirlo entre comillas porque contiene espacios). `list` los muestra todos.
- Con `all`, pulsar Enter (o cerrar la entrada) deja la entrada pendiente y pasa a la siguiente; el CSV se guarda **tras cada respuesta**, así que se puede interrumpir en cualquier momento sin perder lo decidido.

Qué hace cada respuesta:

- **`yes`**: `Aprobado="Sí"` y se **reinicia `Revisado`**. El siguiente `update.py` **reutiliza el veredicto guardado** (sin nueva llamada LLM de revisión) pero **sí evalúa si la entrada es duplicada** (fusión aditiva si casa con algo ya publicado) y le **asigna el tipo** si es nueva (una única llamada LLM de clasificación).
- **`no`**: `Aprobado="No"`. El generador la reexamina en cada ejecución **sin coste de LLM** (por si algún día se cambia a mano), pero no se publica.

Los códigos de salida: 0 si todo fue bien, 1 si hay un problema de datos (identificador inexistente, CSV ausente...), 2 si el uso es incorrecto (respuesta no válida, campo desconocido...).

## Puntos publicados (por `idnum`)

El GeoJSON de trabajo (`map_data.geojson`) es la fuente de verdad de lo publicado: el generador arrastra sus features tal cual en cada ejecución. `review.py` edita y retira los puntos sobre ese archivo (y refleja el cambio en `map_data.csv`, para que ni un update ni un reset lo deshagan).

```bash
python3 review.py point <idnum>                        # mostrar el punto
python3 review.py point <idnum> set <campo> <valor>    # corregir un campo
python3 review.py point <idnum> retract               # retirar el punto (pide confirmación)
python3 review.py point <idnum> retract yes            # retirarlo sin preguntar
```

### Campos editables con `set`

| Campo | Propiedad del GeoJSON | Columna del CSV |
|---|---|---|
| `name` | `nombre` | `Nombre del lugar` |
| `description` | `descrip` | `Descripción` |
| `link` | `enlace` | `Enlace` |
| `type` | `tipo` (código corto) | `Tipo` (nombre largo) |
| `floor` (alias `plant`) | `planta` | `Planta` |
| `latitude` | coordenada | `Coordenadas: latitud` |
| `longitude` | coordenada | `Coordenadas: longitud` |

Notas:

- `type` acepta el **nombre largo** (`"Cafetería, fuente o máquina"`) o el **código corto** (`cafete`); imprime la lista de válidos si se equivoca.
- `floor` aplica la misma transformación que el generador (`Baja`/`Sótano` en minúsculas; `Planta 2` → `2`).
- Al cambiar `latitude`/`longitude`, **campus y edificio no se re-infieren**: si el punto cambió de edificio, lo limpio es retirarlo y volver a aprobar la fila origen.
- `idnum`, `campus`, `edificio` y `clase` **no son editables**: forman parte de la identidad pública del punto. Para cambiarlos, retirar el punto y volver a aprobar la fila.
- Tras cada `set` conviene lanzar `update.py` para publicar el cambio en la web.

### Retirada con `retract`

`retract` **elimina el punto del mapa para siempre**:

1. Muestra el punto y las filas del CSV que se van a dar de baja (la fila origen **y las filas que se habían fusionado en ese punto**).
2. Pide confirmación (escribir `yes`; con el tercer argumento `yes` no pregunta).
3. Antes de tocar nada, copia `map_data.geojson`, `log.json` y `map_data.csv` a `gen_geojson/backups/review_<fecha>/`.
4. Todo junto o nada: quita la feature del GeoJSON de trabajo, pone las filas afectadas a `Aprobado="No"` (así **ni el update ni un reset las ressucitan**) y borra sus Timestamps de `procesados` en `log.json`.
5. Recuerda lanzar `update.py` para publicar la retirada en la web.

Se niega a retirar si es el único punto del mapa (eso es territory del `reset.py`: las guardas de coherencia del generador lo exigen) o si no puede identificar la fila origen con seguridad; en ese caso no cambia nada y sugiere revisarlo a mano.

## Detalles de diseño

- **Respaldos**: toda operación que modifica algo copia antes los archivos afectados a `gen_geojson/backups/review_<fecha>/`. Nunca se pierde el estado anterior.
- **Guardia de dtype (v16)**: antes de escribir el CSV, las columnas que va a tocar se fuerzan a texto; una columna que estuvo vacía se lee como float64 y la escritura abortaría (el error nº 19 del proyecto).
- **Escrituras atómicas**: el GeoJSON y `log.json` se escriben en un `.tmp` y se renombran (`os.replace`): o el archivo viejo o el nuevo, nunca un híbrido.
- **Sin publicar**: `review.py` nunca escribe en la carpeta web; el cambio llega a producción con el siguiente `update.py`.
- Se puede ejecutar desde la raíz del repositorio, desde `commands/` o desde `gen_geojson/` (autodetecta la carpeta del proyecto; también respeta `GADIRE_RUTA_PROYECTO`, como `pipeline.py`).
