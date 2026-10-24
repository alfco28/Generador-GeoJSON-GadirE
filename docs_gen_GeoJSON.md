# Generador del GeoJSON

Este proyecto tiene por finalidad facilitar el generar desde cero y actualizar el archivo GeoJSON que contiene los datos del mapa usado en el proyecto *GadirE*.

El programa principal es `generador_map_data.py` (los cuadernos Jupyter fueron eliminados del repositorio); en el servidor de producción se ejecuta ese mismo archivo.

## Entrada

Al ejecutarse, tomará cinco archivos:

### `map_data.csv`

Necesario. Es el CSV moderado que produce `adecuacion.py`, con las columnas del formulario de aportes más las tres añadidas por la moderación:

- `Timestamp` (clave única de cada fila).
- `Nombre del lugar`.
- `Descripción`.
- `Enlace`.
- `Planta`.
- `Coordenadas: latitud`.
- `Coordenadas: longitud`.
- `Mérito`, `Correo UCA`, `Nombre y apellido/s`, `Protección de datos` (no las emplea el generador).
- `Revisado`.
- `Aprobado`.
- `Tipo`.

De ellas, el generador solo emplea: `Nombre del lugar`, `Descripción`, `Enlace`, `Planta`, `Coordenadas: latitud`, `Coordenadas: longitud`, `Aprobado` y `Tipo`.

Si en algún elemento alguna de estas columnas está vacía, se establecerá la cadena vacía como resultado para la columna y elemento correspondiente.

Está pensado para que se obtenga a partir de un formulario que rellenen los usuarios, reportando así la falta de lugares en el mapa.

**Procesamiento incremental**: solo se procesan las filas con **índice mayor que `ultima_fila_procesada`** (según `log.json`) **y** con `Aprobado` igual a `"Sí"` (la comparación ignora mayúsculas/minúsculas y espacios extremos). El resto de filas no genera feature, pero sí avanzan el contador de filas procesadas.

### `campus.kml` y `edificios.kml`

Necesarios. Polígonos de los campus y de los edificios, usados para inferir el campus y el edificio de cada lugar a partir de sus coordenadas (`Point.within(polygon)`, interior estricto: un punto justo sobre el borde puede quedar sin asignar). Cada polígono debe llevar un `<name>` con el nombre exacto del campus o edificio, coincidente con las claves de `campus_codes`/`edificio_codes` establecidas al principio del programa. Para crearlos o editarlos, empléese `editor_kml.html` (ver `docs_editor_kml.md`).

### `map_data.geojson`

Opcional. Si es dado, se actualizará añadiendo los puntos del mapa nuevos que aparezcan en `map_data.csv`, i.e., los que no estaban ya de antes de acuerdo con `log.json`. El programa no realiza ninguna acción sobre su contenido inicial más que copiarlo para conservarlo en el futuro `map_data.geojson`.

### `log.json`

Opcional. No está pensado para ser creado manualmente, sino por este mismo programa. Lleva un registro de la última línea del CSV que se añadió en el GeoJSON, así como de los índices de cada (tipo, planta, edificio, campus).

## Salida

### `map_data.geojson`

Archivo con los datos del mapa, compatible con el sistema de funcionamiento de *GadirE*. Listo para ser incluido en la carpeta `data` de *GadirE*. Las coordenadas se redondean a **6 decimales** (≈11 cm).

### `log.json`

Archivo que lleva un registro de los lugares que ya se han incluido anteriormente en `map_data.geojson`.

## Funcionamiento externo

Está pensado para que se incluya en una carpeta el archivo principal del proyecto (`generador_map_data.py`), `map_data.csv` y los dos KML (`campus.kml` y `edificios.kml`).

- Si se necesita crear por primera vez el archivo `map_data.geojson`, ejecútese el programa al completo y por orden. Se crearán en la carpeta los archivos `map_data.geojson` y `log.json`.
- Si se necesita actualizar el archivo `map_data.geojson`, ejecútese de nuevo. Se sobreescribirán los archivos `map_data.geojson` y `log.json`.
- El proceso es **idempotente**: reejecutar sin filas nuevas (o sin filas aprobadas nuevas) no cambia el resultado.

Déjense estos seis archivos en la misma carpeta siempre, y cópiese `map_data.geojson` en la carpeta `data` de *GadirE*.

### Exclusión de lugares sin campus o edificio

Las filas cuyo campus o edificio no puedan inferirse de las coordenadas (queden como `None` o `"Desconocido"`) **no generan feature**: se excluyen del GeoJSON, no consumen número de `idnum`, pero **sí cuentan como procesadas** (no se reexaminarán en ejecuciones futuras).

### Comportamientos inesperados

No se hagan combinaciones diferentes a las mencionadas en cuanto a la existencia o no de los mencionados archivos, podría resultar en comportamientos inesperados, pérdida de información en el archivo `map_data.geojson` o información errónea en `map_data.geojson` y/o `log.json`. En particular, **jamás se elimine uno solo de los dos archivos de estado**:

- Eliminar `map_data.geojson` dejando `log.json` → el programa entiende que no queda nada pendiente y produce un **GeoJSON vacío (0 features)**.
- Eliminar `log.json` dejando el `map_data.geojson` antiguo → el programa reprocesa filas ya publicadas y las mezcla con las features existentes, produciendo **duplicados y features fantasma**.

## Regeneración completa (mantenimiento)

Empezar de cero no es una medida de emergencia, sino el mecanismo normal de mantenimiento. Para regenerar, déjense únicamente el programa y `map_data.csv`, y elimínense **juntos** `map_data.geojson` y `log.json`:

```bash
rm -f log.json map_data.geojson
```

(En el servidor de producción los archivos de estado suelen pertenecer a root, pues los crea el cron; allí empléese `sudo rm -f`. El `rm` interactivo, sin `-f`, pregunta y por defecto NO borra archivos protegidos.)

Ejecutado después el programa, el resultado es un GeoJSON **1:1 con las filas `Aprobado == "Sí"` del CSV**, con estas garantías:

- Se **purgan** las features fantasma (puntos duplicados o apilados que no corresponden a ninguna fila actual del CSV).
- Se **recuperan** las filas aprobadas demasiado tarde (ver la trampa de `ultima_fila`, abajo).
- Se **reparan** los `log.json` corruptos o editados a mano.
- Los `idnum` de las filas válidas se **reproducen idénticos** (los identificadores siguen siendo estables).

**Regenerése siempre que:**

- Se aprueben o veten filas a mano en `map_data.csv` (en particular filas antiguas).
- Se sospeche de duplicados o puntos corruptos.
- El `log.json` presente contadores extraños.

### La trampa de `ultima_fila`

Solo se procesan las filas con índice mayor que `ultima_fila_procesada`. Si se aprueba a mano una fila cuyo índice ya quedó atrás (p. ej. un `"Revisar manualmente"` resuelto tiempo después), el flujo incremental jamás la publicará. La solución es regenerar tras cualquier edición manual de filas ya procesadas.

## Funcionamiento interno

Los lugares, *features*, que se crean en `map_data.geojson` tienen la forma:

```
{
    "type": "Feature",
    "properties": {
        "clase": "espacio",
        "nombre": nombre_lugar,
        "descrip": descripcion,
        "enlace": enlace,
        "tipo": tipo_codes_str.get(tipo, ""),
        "planta": planta_value,
        "edificio": edificio,
        "campus": campus,
        "idnum": id_formateado,
    },
    "geometry": {
        "type": "Point",
        "coordinates": [longitud_redondeada, latitud_redondeada]
    }
}
```

Respecto a `idnum`: sigue la estructura `CEEPPTTII`, donde:

- `C` representa un dígito para identificar el campus.
- `EE` representa dos dígitos para identificar el edificio.
- `PP` representa dos dígitos para identificar la planta.
- `TT` representa dos dígitos para identificar el tipo.
- `II` representa dos dígitos para identificar el índice del *feature* en un mismo campus, edificio, planta y tipo dados.

La identificación de cada elemento se lleva a cabo mediante las biyecciones establecidas al principio del programa.

Considérense las limitaciones que puedan implicar este sistema de numeración.

Este sistema de numeración es el que usa *GadirE* para determinar y distinguir los *features*. Es indispensable que `map_data.geojson` no contenga dos *features* con el mismo `idnum`; este programa cumple con esa condición dentro de sus límites, y la regeneración completa restablece esa garantía partiendo del CSV.