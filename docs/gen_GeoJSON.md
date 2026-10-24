# Generador del GeoJSON

Este proyecto tiene por finalidad facilitar el generar desde cero y actualizar el archivo GeoJSON que contiene los datos del mapa usado en el proyecto *GadirE*. Lo forman dos programas de Python —`adecuacion.py` (moderación de los aportes) y `generador_map_data.py` (generación del GeoJSON)—, el módulo `dedup.py` (deduplicación con fusión aditiva, compartido por ambos; ver `dedup.md`), el módulo `registro.py` y los scripts de operación (`update.py`, `reset.py`, `calendario.py`, `cron.py`, `estado.py`; ver `ops.md`), y una herramienta auxiliar, el editor de KML de `kml_editor/`, para crear y editar los polígonos de campus y edificios (ver `kml_editor.md`).

## El flujo de trabajo

### 1. Preprocesamiento (`adecuacion.py`)

- **Entrada**: `map_data_form.csv` (lugares reportados por los usuarios en el formulario).
- **Salida**: `map_data.csv` (lugares validados, clasificados y con el tipo corregido).
- **Proceso**:
  - Revisa cada fila **aún no revisada** para determinar si el contenido es adecuado (usando Ollama); reutiliza los valores válidos de `Aprobado` ya existentes y respeta las ediciones manuales.
  - Clasifica el tipo de lugar (ej: "Aula", "Cafetería, fuente o máquina").
  - Corrige el tipo para que coincida exactamente con los predefinidos (coincidencia exacta → subcadena → distancia de Levenshtein ≤ 3; si no, `"Revisar manualmente"`).
  - Guarda el resultado en `map_data.csv` con las columnas adicionales `Revisado`, `Aprobado` y `Tipo`.

### 2. Generación del GeoJSON (`generador_map_data.py`)

- **Entrada**: `map_data.csv`, `campus.kml` y `edificios.kml`, `map_data.geojson` (opcional) y `log.json` (opcional).
- **Salida**: `map_data.geojson` y `log.json`.
- **Proceso**:
  - Procesa solo las filas cuyo `Timestamp` no esté ya publicado (incremental, ver abajo) **y** con `Aprobado == "Sí"`.
  - Infiere el campus y el edificio de cada lugar usando los KML.
  - **Excluye los lugares con campus o edificio `None` o `"Desconocido"`**: no generan feature, no consumen número de `idnum` y se reexaminan en cada ejecución.
  - **Deduplica con fusión aditiva**: un aporte que repita un punto existente NO crea feature ni `idnum` nuevo; su información nueva se AÑADE a la feature existente (ver `dedup.md`).
  - Genera un `idnum` único para cada lugar creado y lo combina con las features ya existentes.

## Requisitos y dependencias

- **Python** (probado en 3.9 y 3.13).
- Librerías: `pip install pandas ollama python-Levenshtein unidecode geopandas shapely`.
- **Ollama** (solo para `adecuacion.py`): el modelo está **fijado en el código** (constante `modelo` en `adecuacion.py`): **`mistral:7b`** (~4,4 GB). Descargarlo con `ollama pull mistral:7b` y tener el servicio en ejecución (`ollama serve`). Que `ollama ps` salga vacío es normal: el modelo se descarga de memoria tras un rato de inactividad, y la primera llamada en frío tarda unos 8 segundos.
- Enlaces útiles: [Ollama en GitHub](https://github.com/jmorganca/ollama).

## Entrada

Al ejecutarse, `generador_map_data.py` tomará cinco archivos:

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
- `Duplicado de` (dedup): el `idnum` del gemelo publicado o el `Timestamp` del gemelo del lote, cuando el aporte repite un punto ya conocido (la escribe sólo `adecuacion.py`, y el generador la verifica contra el grupo antes de fusionar).

De ellas, el generador emplea: `Timestamp` (para el incremental), `Nombre del lugar`, `Descripción`, `Enlace`, `Planta`, `Coordenadas: latitud`, `Coordenadas: longitud`, `Aprobado` y `Tipo`. Si alguna de estas columnas está vacía en un elemento, se establece la cadena vacía como resultado.

Está pensado para que se obtenga a partir de un formulario que rellenen los usuarios, reportando la falta de lugares en el mapa.

### `campus.kml` y `edificios.kml`

Necesarios. Polígonos de los campus y de los edificios, usados para inferir el campus y el edificio de cada lugar a partir de sus coordenadas (`Point.within(polygon)`, interior estricto: un punto justo sobre el borde puede quedar sin asignar). Cada polígono debe llevar una etiqueta `<name>` con el nombre **exacto** del campus o edificio, coincidente con las claves de `campus_codes`/`edificio_codes` (y, para los edificios, con el conjunto de su campus): un acento o un espacio de más deja los lugares sin asignar. Para crearlos o editarlos, empléese el editor de `kml_editor/` (ver `kml_editor.md`); como alternativa, [Google My Maps](https://www.google.com/maps/about/mymaps/) permite dibujarlos y exportarlos como KML.

### `map_data.geojson`

Opcional. Si es dado, se actualizará añadiendo los puntos nuevos que aparezcan en `map_data.csv`, i.e., los que no estaban ya de antes de acuerdo con `log.json`. El programa no realiza ninguna acción sobre su contenido inicial más que copiarlo para conservarlo en el futuro `map_data.geojson`.

### `log.json`

Opcional. No está pensado para ser creado manualmente, sino por este mismo programa. Lleva el registro (`procesados`) de los `Timestamp` ya publicados en el GeoJSON, así como los contadores de IDs (`id_counter`) de cada (campus, edificio, planta, tipo). Si falta o está corrupto, se entiende que también se ha borrado `map_data.geojson` y se regenera de cero; si tiene el **formato antiguo** (sin `procesados`), el programa aborta pidiendo el reset, para no duplicar el mapa. Desde v14 hay además **guardas de coherencia**: si se ha borrado un archivo de estado sin el otro (log sin geojson → mapa vacío; geojson sin log → duplicados), el programa aborta con un mensaje claro en lugar de corromper el mapa.

## Salida

### `map_data.geojson`

Archivo con los datos del mapa, compatible con el sistema de funcionamiento de *GadirE*. Listo para ser incluido en la carpeta `data` de *GadirE*. Solo se incluyen los lugares con `campus` y `edificio` asignados (distintos de `None` y de `"Desconocido"`); las coordenadas se redondean a **6 decimales** (≈11 cm). Su estructura se detalla en «Funcionamiento interno».

### `log.json`

Registro de progreso, contadores de IDs y auditoría completa (deduplicación y ejecuciones). Ejemplo (formato v14):

```json
{
    "procesados": [
        "2026/10/12 12:34:56",
        "2026/10/12 12:40:11"
    ],
    "id_counter": {
        "Puerto Real": {
            "Facultad de Ciencias": {
                "Baja": {
                    "Cafetería, fuente o máquina": 2
                }
            }
        }
    },
    "fusiones": [
        {"timestamp": "...", "idnum": "330100501", "campos_actualizados": ["descrip", "enlace"], "alias": "Punto de carga VE FC"}
    ],
    "avisos_duplicados": [
        {"timestamp": "...", "idnum_existente": "308010401", "distancia_m": 263.1}
    ],
    "ejecuciones": [
        {"fecha": "2026-10-24T14:43:50", "modo": "update", "duracion_s": 3.2,
         "filas_csv": 14, "no_aprobadas": 1, "ya_publicadas": 10, "publicadas": 1,
         "fusionadas": 1, "excluidas_sin_ubicacion": 1, "features_finales": 9,
         "fusiones_esta_ejecucion": ["..."], "avisos_esta_ejecucion": ["..."],
         "idnums_asignados": {"...": "229010301"},
         "resumen_adecuacion": {"llm_revision": 2, "llm_clasificacion": 1, "...": "..."}}
    ]
}
```

Cada ejecución del generador añade su entrada completa a `ejecuciones` (modo `update`/`reset`/`manual`, duración, qué le pasó a cada fila, `idnum` asignados, fusiones y avisos de esa pasada, y el resumen de la moderación si la hubo). El texto completo de cada ejecución, con las respuestas crudas del LLM y las decisiones fila a fila, queda en los logs de `logs/` (ver `ops.md`).

## Funcionamiento externo

Está pensado para que se incluya en una carpeta el archivo principal del proyecto (`generador_map_data.py`), `map_data.csv` y los dos KML (`campus.kml` y `edificios.kml`).

- Si se necesita crear por primera vez el archivo `map_data.geojson`, ejecútese el programa al completo y por orden. Se crearán en la carpeta los archivos `map_data.geojson` y `log.json`.
- Si se necesita actualizar el archivo `map_data.geojson`, ejecútese de nuevo. Se sobreescribirán los archivos `map_data.geojson` y `log.json`.
- El proceso es **idempotente**: reejecutar sin filas aprobadas nuevas no cambia el resultado.

Déjense estos seis archivos en la misma carpeta siempre, y cópiese `map_data.geojson` en la carpeta `data` de *GadirE*.

### Procesamiento incremental (por `Timestamp`)

El incremental es **por `Timestamp`**, la clave única de cada aporte, y no por posición: los aportes nuevos del formulario entran por arriba en la hoja y desplazan las filas viejas, de modo que un índice posicional volvería a procesar filas ya publicadas (duplicando features) o se dejaría otras sin procesar jamás. Solo se procesan las filas cuyo `Timestamp` no esté ya en `procesados` **y** con `Aprobado` igual a `"Sí"` (la comparación ignora mayúsculas/minúsculas y espacios extremos).

Las filas **no aprobadas no se marcan como procesadas**: se reexaminan en cada ejecución (sin coste, aquí no hay modelo de lenguaje), de modo que aprobar a mano una fila `Revisar manualmente` —o cambiar un `No` por un `Sí`— la publica en la siguiente ejecución sin más.

### Exclusión de lugares sin campus o edificio

Las filas cuyo campus o edificio no puedan inferirse de las coordenadas (queden como `None` o `"Desconocido"`) **no generan feature**: se excluyen del GeoJSON y no consumen número de `idnum`, pero se **reexaminan en cada ejecución**, de modo que en cuanto se les pueda asignar campus y edificio (p. ej. tras mejorar los KML) se publican solas.

## Reset (mantenimiento)

Empezar de cero no es una medida de emergencia, sino el mecanismo normal de mantenimiento. El nombre definitivo de la regeneración completa es **reset**. La vía normal es el script:

```bash
sudo python3 reset.py
```

Pide confirmación escribiendo exactamente `GadirE`, respalda los dos archivos de estado en `backups/` y los borra **juntos**, y después ejecuta el pipeline completo en modo `reset`. `map_data.csv` no se toca (guarda los veredictos manuales, que la moderación reutiliza).

A mano equivaldría a: dejar únicamente el programa y `map_data.csv`, y eliminar **juntos** `map_data.geojson` y `log.json` con `sudo rm -f` (el `rm` interactivo, sin `-f`, pregunta y por defecto NO borra archivos protegidos) y volver a ejecutar. **Nunca se borra uno sin el otro**: desde v14 el generador lo detecta y aborta, en lugar de publicar un mapa vacío o duplicar todo.

Ejecutado después el programa, el resultado es un GeoJSON **1:1 con las filas `Aprobado == "Sí"` del CSV**, con estas garantías:

- Se **purgan** las features fantasma (puntos duplicados o apilados que no corresponden a ninguna fila actual del CSV).
- Se **recuperan** las filas aprobadas demasiado tarde (con el incremental por `Timestamp` la siguiente ejecución ya las publica por sí sola; el reset es la vía inmediata).
- Se **reparan** los `log.json` corruptos o editados a mano.
- Los `idnum` de las filas válidas se **reproducen idénticos** (los identificadores siguen siendo estables).

**Hágase reset siempre que:**

- Se aprueben o veten filas a mano en `map_data.csv` (con el incremental por `Timestamp` no es estrictamente necesario, pero garantiza un GeoJSON 1:1 con el CSV).
- Se sospeche de duplicados o puntos corruptos.
- El `log.json` presente contadores extraños o el formato antiguo.

### Ediciones manuales de filas ya procesadas

El incremental es por `Timestamp`, no por posición: una fila antigua aprobada o vetada a mano (p. ej. un `Revisar manualmente` resuelto tiempo después) se publica por sí sola en la siguiente ejecución, porque su `Timestamp` no consta en `procesados`. Hacer reset tras editar filas a mano sigue siendo recomendable para obtener un GeoJSON 1:1 con el CSV de una vez.

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

La propiedad `planta` guarda `baja`/`sótano` en minúsculas para esas plantas, y para el resto la última palabra del campo (p. ej. `Planta 2` → `2`).

Respecto a `idnum`: sigue la estructura `CEEPPTTII`, donde:

- `C` representa un dígito para identificar el campus (`campus_codes`; ej.: `Cádiz = "0"`, `Jerez = "1"`, `Bahía de Algeciras = "2"`, `Puerto Real = "3"`).
- `EE` representa dos dígitos para identificar el edificio (`edificio_codes`; ej.: `Facultad de Ciencias = "30"`).
- `PP` representa dos dígitos para identificar la planta (`planta_codes`; ej.: `"1" = "01"`, `"Baja" = "10"`, `"Sótano" = "11"`).
- `TT` representa dos dígitos para identificar el tipo (`tipo_codes_num`; ej.: `"Aula" = "03"`, `"Cafetería, fuente o máquina" = "05"`).
- `II` representa dos dígitos para identificar el índice del *feature* en un mismo campus, edificio, planta y tipo dados.

La identificación de cada elemento se lleva a cabo mediante las biyecciones establecidas al principio del programa. Considérense las limitaciones que pueda implicar este sistema de numeración (dos dígitos por campo: a lo sumo 99 edificios, 99 índices por combinación campus-edificio-planta-tipo, etc.).

Este sistema de numeración es el que usa *GadirE* para determinar y distinguir los *features*. Es indispensable que `map_data.geojson` no contenga dos *features* con el mismo `idnum`; este programa cumple con esa condición dentro de sus límites, y el reset restablece esa garantía partiendo del CSV.

## Configuración y personalización

- **Tipos de lugares**: definidos en `adecuacion.py` (variable `tipos`). Para adaptar el sistema a otra universidad, modifíquese esa lista y los códigos asociados (`tipo_codes_num`, `tipo_codes_str`).
- **Códigos de campus, edificios y plantas**: definidos en `generador_map_data.py` (`campus_codes`, `edificio_codes`, `planta_codes`), junto con los conjuntos de edificios de cada campus (`campusBahiaAlgeciras`, `campusCadiz`, `campusJerez`, `campusPuertoReal`), que filtran los edificios candidatos al inferir el edificio de un punto.
- El valor de `Planta` en el CSV debe coincidir con las claves de `planta_codes` (ej.: `1`, `Baja`, `Sótano`).
- Los códigos deben ser **únicos y consistentes**; el `idnum` se genera como `CEEPPTTII`.

## Casos de uso

### Crear el GeoJSON desde cero

1. Colocar `map_data_form.csv` en la carpeta.
2. Ejecutar `adecuacion.py` → genera `map_data.csv`.
3. Ejecutar `generador_map_data.py` → genera `map_data.geojson` y `log.json`.

### Actualizar el GeoJSON existente

1. Añadir nuevas filas a `map_data_form.csv`.
2. Ejecutar `adecuacion.py` → actualiza `map_data.csv`.
3. Ejecutar `generador_map_data.py` → actualiza `map_data.geojson` y `log.json` (sin duplicar lugares ya publicados).

### Actualizar los polígonos de campus/edificios

1. Abrir `kml_editor/kml_editor.html` en el navegador e importar los KML actuales del repositorio (la importación conserva el orden).
2. Editar los polígonos: mover vértices, renombrar, añadir, eliminar, reordenar.
3. Descargar los dos archivos y sustituir `campus.kml` y `edificios.kml` en la carpeta.
4. Si se han añadido, eliminado o renombrado edificios o campus, actualizar también `generador_map_data.py` (`edificio_codes`/`campus_codes` y los conjuntos de edificios por campus); el botón *Copy Python codes* del editor genera los diccionarios ya renumerados.
5. **Hacer reset** (borrar `log.json` y `map_data.geojson` **juntos** y ejecutar de nuevo; o directamente `sudo python3 reset.py`): el incremental solo publica filas nuevas, de modo que sin reset las features existentes no se reubican con los polígonos nuevos.

## Despliegue en el servidor (producción)

El backend de producción es un **clon de este repositorio** con su propio entorno virtual (no una carpeta copiada a mano), servido por el servidor web tras HTTPS. El flujo lo orquestan dos scripts de servidor (documentados en la guía de despliegue, no en este repositorio):

- **`actualizar_mapa.sh`**: activa el venv → descarga el CSV publicado del formulario (`map_data_form.csv`) → ejecuta `adecuacion.py` y `generador_map_data.py` → publica `map_data.geojson` en la carpeta servida, con permisos de lectura → registra todo en su log.
- **`actualiza_calendario_pre_ceuca.sh`**: descarga el ICS del calendario con **descarga atómica** (a un `.tmp` y luego `mv`; si falla, el archivo servido queda intacto) y lo publica junto al resto de `data/`.

**Cron** (ejemplo):

```
0 4 * * 1-5     actualizar_mapa.sh                   # mapa, de lunes a viernes
30 4 * * *      actualiza_calendario_pre_ceuca.sh    # calendario, a diario
```

Comprobar la zona horaria del servidor antes de fiarse de las horas: los cron usan la hora local del servidor.

### Interacción con el despliegue del frontend

El despliegue del frontend **sobrescribe la carpeta `data/` servida**, incluido `map_data.geojson`. Por eso:

1. Cada release del frontend debería llevar el `map_data.geojson` **actualizado desde producción** (ver abajo).
2. Tras cada deploy del frontend, **relanzar `actualizar_mapa.sh`** (o excluir `data/` del deploy), para no dejar en la web un GeoJSON más viejo que el del cron.

La fuente canónica del dato es **la producción** (la salida del cron). Para llevarla al repo del frontend:

```bash
curl -o data/map_data.geojson https://gadire.alfeva.net/data/map_data.geojson
```

Verificación rápida antes de commitear:

```bash
python3 -c "import json; d=json.load(open('data/map_data.geojson')); fs=d['features']; print(len(fs), 'features'); assert len({f['properties']['idnum'] for f in fs})==len(fs); assert all(f['properties']['campus'] and f['properties']['campus']!='Desconocido' for f in fs); print('OK')"
```

Tras cambiar el GeoJSON, recordar el **bump de la caché del service worker** (`CACHE_NAME` en `sw.js`) para que los clientes lo refresquen.

## Limitaciones y consideraciones

1. **Inferencia geográfica**: la precisión depende de la calidad de los polígonos de los KML; `within` exige el interior estricto, así que un punto justo sobre un borde puede quedar sin asignar. Los lugares fuera de todo polígono se excluyen del GeoJSON y se reexaminan en cada ejecución hasta que se les pueda asignar uno.
2. **Modelo de lenguaje**: la clasificación y revisión dependen del modelo; puede requerir ajustes en el prompt (los falsos positivos existen: ver la validación manual). Si el modelo devuelve un tipo no predefinido, se corrige automáticamente.
3. **Validación manual**: revisar siempre los lugares marcados como `Revisar manualmente` en `map_data.csv` y resolverlos (`"Sí"` o `"No"`); el incremental los publicará (o no) en la siguiente ejecución, y el reset deja el GeoJSON 1:1 con el CSV.
4. **IDs únicos**: el sistema garantiza IDs únicos dentro de un mismo (campus, edificio, planta, tipo). No se garantiza unicidad global si se modifican manualmente los archivos de estado; ante la duda, hacer reset.
5. **Rendimiento**: procesar muchos lugares puede ser lento por las llamadas al modelo de lenguaje (solo se revisa lo nuevo, así que el coste es incremental).

## Ejemplo práctico (Universidad de Cádiz)

Aporte del formulario (`map_data_form.csv`): `Nombre del lugar` = «Cafetería de la ETSIA», `Planta` = «Baja», `Coordenadas: latitud` = 36.136672, `Coordenadas: longitud` = −5.453441, con `Aprobado = "Sí"` y `Tipo = "Cafetería, fuente o máquina"` tras la moderación.

Feature generado en `map_data.geojson`:

```json
{
    "type": "Feature",
    "properties": {
        "clase": "espacio",
        "nombre": "Cafetería de la ETSIA",
        "descrip": "",
        "enlace": "",
        "tipo": "cafete",
        "planta": "baja",
        "edificio": "Escuela Técnica Superior de Ingeniería de Algeciras (ETSIA)",
        "campus": "Bahía de Algeciras",
        "idnum": "229100501"
    },
    "geometry": {
        "type": "Point",
        "coordinates": [-5.453441, 36.136672]
    }
}
```

Su `idnum` se descompone como `2` (Bahía de Algeciras) + `29` (ETSIA) + `10` (Baja) + `05` (Cafetería, fuente o máquina) + `01` (primera cafetería de la ETSIA en planta baja). Si el lugar quedara con campus o edificio sin asignar (`None` o `"Desconocido"`), **no se incluiría en el GeoJSON**, pero seguiría reexaminándose en cada ejecución.

## Solución de problemas

| Problema | Posible causa | Solución |
|---|---|---|
| Error al cargar KML | Archivo KML mal formado o inexistente. | Verificar que los KML existan y tengan polígonos con la etiqueta `<name>`. |
| Ollama no responde | Servicio no iniciado o modelo no descargado. | Ejecutar `ollama serve` y descargar el modelo (`ollama pull mistral:7b`). |
| `ModuleNotFoundError` | El entorno virtual no está activado. | Activar el venv antes de ejecutar los scripts. |
| Error: `log.json` con formato antiguo | El log es de la versión posicional (sin `procesados`). | Borrar `log.json` y `map_data.geojson` **juntos** y volver a ejecutar. |
| IDs duplicados | `log.json` corrupto o editado a mano. | Hacer reset: borrar ambos archivos juntos y ejecutar de nuevo. |
| GeoJSON vacío (0 features) | Se borró `map_data.geojson` pero no `log.json`. | Borrar **ambos** archivos y ejecutar de nuevo. |
| Features duplicadas o fantasma | Se borró `log.json` pero no el `map_data.geojson` viejo. | Borrar **ambos** y ejecutar de nuevo (el reset las purga). Ya no puede volver a pasar: el generador aborta si se borra uno solo. |
| Un lugar aprobado no aparece | El incremental aún no ha vuelto a ejecutarse. | Ejecutar de nuevo (el incremental por `Timestamp` publica solo las filas aprobadas a mano); si persiste, hacer reset. |
| Lugares sin campus/edificio en el GeoJSON | Coordenadas fuera de los polígonos. | Revisar los KML o añadir polígonos; el lugar queda excluido y se reexamina en cada ejecución hasta poder asignarse. |
| `rm` no borra los archivos de estado | Pertenecen a root (p. ej. los crea un cron) y `rm` pregunta. | Usar `sudo rm -f`, o mejor `sudo python3 reset.py`. |
| Se borró un archivo de estado sin el otro | Incoherencia log/geojson (mapa vacío o duplicados). | Desde v14 el generador aborta con un mensaje claro; hacer reset (`sudo python3 reset.py`) para reconstruir. |
| Coordenadas vacías o no numéricas en una fila | El formulario no rellenó el GPS. | No rompe nada (v14): se toman como (0, 0) y la fila queda excluida y reexaminada; quedar registrado en el log. |