# Documentación del Sistema de Generación de GeoJSON para mapas universitarios

---

## 📌 Introducción

Este proyecto permite **generar y actualizar** un archivo **GeoJSON** con datos georreferenciados de lugares en un campus universitario, diseñado para ser compatible con sistemas como *GadirE*. El proceso se divide en dos scripts principales:

1. **`adecuacion.py`**: Procesa un CSV de entrada, revisa y clasifica los lugares usando un modelo de lenguaje local (Ollama), y genera un CSV intermedio con los datos validados y clasificados.
2. **`generador_map_data.py`**: Toma el CSV procesado, infiere campus y edificios a partir de coordenadas, y genera el GeoJSON final con identificadores únicos, **excluyendo lugares con campus o edificio sin asignar (`None`) o `"Desconocido"`**.

> **Nota sobre los notebooks**: los dos programas existen como cuadernos Jupyter (`.ipynb`) y como exportes a Python (`.py`). En el servidor de producción se ejecutan los `.py`. **Cualquier cambio debe aplicarse a ambas versiones** (`.ipynb` y `.py`) para que no se desincronicen.

---

## 📂 Estructura del Proyecto

```
├── adecuacion.ipynb         # Cuaderno: preprocesamiento y clasificación
├── adecuacion.py            # Exporte del cuaderno anterior
├── generador_map_data.ipynb # Cuaderno: generación del GeoJSON
├── generador_map_data.py    # Exporte del cuaderno anterior
├── campus.kml                # Polígonos de los campus (inferencia geográfica)
├── edificios.kml             # Polígonos de los edificios (inferencia geográfica)
├── map_data_form.csv         # CSV de entrada (aportes del formulario de usuarios)
├── map_data.csv              # CSV intermedio (generado por adecuacion.py)
├── map_data.geojson          # GeoJSON final (generado por generador_map_data.py)
├── log.json                  # Estado incremental del generador
├── docs_gen_GeoJSON.md       # Documentación interna del generador
└── LICENSE
```

---

## 🔄 Flujo de Trabajo

### 1. Preprocesamiento (`adecuacion.py`)
- **Entrada**: `map_data_form.csv` (lugares reportados por usuarios).
- **Salida**: `map_data.csv` (lugares validados, clasificados y con tipo corregido).
- **Proceso**:
  - Revisa cada fila **aún no revisada** para determinar si el contenido es adecuado (usando Ollama); reutiliza los valores válidos de `Aprobado` ya existentes y respeta las ediciones manuales.
  - Clasifica el tipo de lugar (ej: "Aula", "Cafetería").
  - Corrige el tipo para que coincida exactamente con los predefinidos (coincidencia exacta → subcadena → distancia de Levenshtein ≤ 3; si no, `"Revisar manualmente"`).
  - Guarda el resultado en `map_data.csv` con columnas adicionales: `Revisado`, `Aprobado`, `Tipo`.

### 2. Generación del GeoJSON (`generador_map_data.py`)
- **Entrada**:
  - `map_data.csv` (lugares validados).
  - `campus.kml` y `edificios.kml` (para inferir campus/edificio a partir de coordenadas).
  - `log.json` (opcional, para continuar desde la última ejecución).
- **Salida**:
  - `map_data.geojson` (GeoJSON con todos los lugares **excluyendo aquellos con campus o edificio `None` o `"Desconocido"`**).
  - `log.json` (registro de progreso y contadores de IDs).
- **Proceso**:
  - Procesa solo las filas con **índice > `ultima_fila_procesada`** (incremental) **y** `Aprobado == "Sí"` (comparación sin distinción de mayúsculas y sin espacios).
  - Infiere el campus y edificio de cada lugar usando los KML.
  - **Excluye lugares con campus o edificio `None` o `"Desconocido"`**: no generan feature, **no consumen número de `idnum`**, pero **sí cuentan como procesadas** (no se reexaminan en cada ejecución).
  - Genera un `idnum` único para cada lugar creado.
  - Combina los nuevos lugares con los existentes (si `map_data.geojson` ya existe).
  - Ordena y guarda el GeoJSON final.
  - El proceso es **idempotente**: reejecutar sin filas nuevas no cambia nada.

---

## 📝 Especificaciones de Entrada/Salida

### Entradas

#### `map_data_form.csv`
Columnas (en este orden): `Timestamp`, `Nombre del lugar`, `Descripción`, `Enlace`, `Planta`, `Coordenadas: latitud`, `Coordenadas: longitud`, `Mérito`, `Correo UCA`, `Nombre y apellido/s`, `Protección de datos`.

- **`Timestamp` es la clave única** que identifica cada fila/aporte.
- **Siempre rellenas (obligatorias)**: `Nombre del lugar`, `Planta`, `Coordenadas: latitud`, `Coordenadas: longitud`.
- **Opcionales**: el resto.
- Este CSV se obtiene del formulario de usuarios (en producción, lo descarga el script del servidor desde un Google Sheets).

#### `campus.kml` y `edificios.kml`
- Archivos KML con polígonos que definen los límites de **campus** y **edificios**.
- Cada polígono debe tener un atributo `Name` con el nombre del campus/edificio (ej: "Facultad de Ciencias").
- **Cómo generarlos**: Usar [Google My Maps](https://www.google.com/maps/about/mymaps/) para dibujar los polígonos y exportarlos como KML.

#### `log.json` (opcional)
- Guarda el progreso:
  - `ultima_fila_procesada`: Última fila del CSV procesada.
  - `id_counter`: Contadores de IDs para cada (campus, edificio, planta, tipo).

---

### Salidas

#### `map_data.csv`
CSV intermedio con columnas adicionales:
- `Revisado`: `"Sí"` si ya fue revisado.
- `Aprobado`: `"Sí"`, `"No"` o `"Revisar manualmente"`.
- `Tipo`: Tipo de lugar (ej: "Aula"), corregido para coincidir con los predefinidos.

#### `map_data.geojson`
GeoJSON con la estructura:
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "clase": "espacio",
        "nombre": "Aula 1.2",
        "descrip": "Aula de informática",
        "enlace": "https://ejemplo.com",
        "tipo": "aula",
        "planta": "1",
        "edificio": "Facultad de Ciencias",
        "campus": "Puerto Real",
        "idnum": "328010301"
      },
      "geometry": {
        "type": "Point",
        "coordinates": [-6.234567, 36.543210]
      }
    }
  ]
}
```
**Nota**: Solo se incluyen lugares con `campus` y `edificio` asignados (distintos de `None` y de `"Desconocido"`). Las coordenadas se redondean a **6 decimales** (≈11 cm).

#### `log.json`
Ejemplo:
```json
{
  "ultima_fila_procesada": 42,
  "id_counter": {
    "Puerto Real": {
      "Facultad de Ciencias": {
        "1": {
          "Aula": 1
        }
      }
    }
  }
}
```

---

## 🔧 Configuración y Personalización

### Tipos de Lugares Predefinidos
Los tipos de lugares están definidos en `adecuacion.py` (variable `tipos`). Ejemplo:
```python
tipos = {
    "Aula": "aulas, seminarios o salas de clase...",
    "Cafetería, fuente o máquina": "cafeterías, fuentes de agua...",
    ...
}
```
- **Para adaptar a otra universidad**: Modificar esta lista y los códigos asociados (`tipo_codes_num`, `tipo_codes_str`).

### Códigos de Campus, Edificios y Plantas
Definidos en `generador_map_data.py`:
- `campus_codes`: Ej: `"Puerto Real": "3"`.
- `edificio_codes`: Ej: `"Facultad de Ciencias": "30"`.
- `planta_codes`: Ej: `"1": "01"`.

**Importante**:
- Los códigos deben ser únicos y consistentes.
- El `idnum` se genera como `CEEPPTTII` (Campus + Edificio + Planta + Tipo + Índice).

### Inferencia Geográfica
- Los KML (`campus.kml`, `edificios.kml`) deben tener polígonos con el atributo `Name` coincidente con los nombres en los códigos.
- Si un lugar no está dentro de ningún polígono, se excluye del GeoJSON (pero se marca como procesado).

---

## 🛠️ Requisitos y Dependencias

### Python
- Probado en **3.9.6** (desarrollo) y **3.13.5** (servidor de producción, Debian 13).

### Librerías
Instalar con:
```bash
pip install pandas ollama python-Levenshtein unidecode geopandas shapely
```

### Ollama
- El modelo está **fijado en el código** (constante `modelo` en `adecuacion.py`): **`mistral:7b`** (~4,4 GB).
- Descargar el modelo: `ollama pull mistral:7b`
- Asegurarse de que el servicio de Ollama esté en ejecución:
  ```bash
  ollama serve
  ```
- `ollama ps` vacío es normal: el modelo se descarga de memoria tras un rato de inactividad. La primera llamada en frío tarda unos 8 segundos.
- **Enlaces útiles**:
  - [Ollama GitHub](https://github.com/jmorganca/ollama)
  - [Documentación de Ollama](https://github.com/jmorganca/ollama#readme)

### Google My Maps (para generar KML)
- [Google My Maps](https://www.google.com/maps/about/mymaps/)
- **Guía rápida**:
  1. Crear un nuevo mapa.
  2. Dibujar polígonos para cada campus/edificio.
  3. Asignar un nombre a cada polígono (ej: "Facultad de Ciencias").
  4. Exportar como KML (Capa → Exportar como KML).

---

## 🚀 Ejecución

### 1. Preprocesamiento (`adecuacion.py`)
```bash
python adecuacion.py
```
- **Entrada**: `map_data_form.csv`.
- **Salida**: `map_data.csv`.

### 2. Generación del GeoJSON (`generador_map_data.py`)
```bash
python generador_map_data.py
```
- **Entrada**: `map_data.csv`, `campus.kml`, `edificios.kml`.
- **Salida**: `map_data.geojson`, `log.json`.

---

## 🔁 Regeneración completa (mantenimiento)

La regeneración (empezar de cero) **no es una emergencia: es el mecanismo normal de mantenimiento**. Genera un GeoJSON 1:1 con las filas `Aprobado == "Sí"` del CSV y:

- **purga features fantasma** (puntos duplicados o apilados sin fila en el CSV actual),
- **recupera filas aprobadas a mano demasiado tarde** (ver la trampa de `ultima_fila`, abajo),
- **repara `log.json` corruptos** (p. ej. contadores con claves erróneas),
- reproduce los mismos `idnum` para las filas válidas (los IDs siguen siendo estables).

**Cuándo regenerar:**
- Tras **aprobar o vetar filas a mano** en `map_data.csv` (especialmente filas antiguas).
- Ante sospecha de duplicados o puntos corruptos.
- Si `log.json` está corrupto o se ha editado a mano.

**Cómo regenerar — regla de oro:**

> **`log.json` y `map_data.geojson` se borran SIEMPRE juntos, y con `rm -f`.**

```bash
rm -f log.json map_data.geojson
python generador_map_data.py
```

**Nunca se borra uno sin el otro.** Los dos modos de fallo son reales y ocurrieron en producción:
- Borrar **solo** `map_data.geojson` (dejando `log.json`): el generador cree que no queda nada pendiente → **GeoJSON vacío (0 features)**.
- Borrar **solo** `log.json` (dejando el GeoJSON viejo): el generador reprocesa filas antiguas y las mezcla con las features existentes → **duplicados y features fantasma**.

En el servidor de producción los archivos de estado suelen pertenecer a root (los crea el cron), así que allí se usa `sudo rm -f` y se relanza el script del mapa (ver la sección de despliegue).

### La trampa de `ultima_fila`

El generador solo examina filas con **índice > `ultima_fila_procesada`**. Si se aprueba a mano una fila **anterior** a ese índice (p. ej. un `"Revisar manualmente"` resuelto semanas después), el flujo incremental **nunca la publicará**. Solución: regenerar tras cualquier edición manual de filas ya pasadas.

### Validación manual

Siempre revisar los lugares marcados como `"Revisar manualmente"` en `map_data.csv` y resolverlos (`"Sí"` o `"No"`), seguido de una regeneración. Ejemplo real: el modelo aprobó un teatro de la ciudad como "Salón de Actos o de Grado" (falso positivo); se vetó a mano (`Aprobado="No"`) y la regeneración lo retiró del mapa.

---

## 🖥️ Despliegue en el servidor (producción, GadirE)

El backend de producción es un **clon de este repositorio** con su propio venv (no una carpeta copiada a mano), servido por nginx tras HTTPS. El flujo lo orquestan dos scripts de servidor (documentados en la guía de despliegue, no en este repo):

- **`actualizar_mapa.sh`**: activa el venv → descarga el CSV publicado del formulario (`map_data_form.csv`) → ejecuta `adecuacion.py` y `generador_map_data.py` → copia `map_data.geojson` a la carpeta servida (`/var/www/Gadire/data/`, con `chown www-data:www-data` y `chmod 644`) → registra todo en `/var/log/actualizar_mapa.log`.
- **`actualiza_calendario_pre_ceuca.sh`**: descarga el ICS del calendario con **descarga atómica** (a un `.tmp` y luego `mv`; si falla, el archivo servido queda intacto) y lo publica junto al resto de `data/`; log en `/var/log/actualizar_calendario.log`.

**Cron de root** (verificado en producción):
```
0 4 * * 1-5     actualizar_mapa.sh                   # mapa, de lunes a viernes
30 4 * * *      actualiza_calendario_pre_ceuca.sh    # calendario, a diario
```
Comprobar la zona horaria del servidor antes de fiarse de las horas: los cron usan la hora local del servidor, y en la instalación actual parece ir en UTC (la actualización del mapa dispara a las 6:00 hora española).

### ⚠️ Interacción con el despliegue del frontend

El despliegue del frontend **sobrescribe la carpeta `data/` servida**, incluido `map_data.geojson`. Por eso:

1. Cada release del frontend debería llevar el `map_data.geojson` **actualizado desde producción** (ver abajo).
2. Tras cada deploy del frontend, **relanzar `actualizar_mapa.sh`** (o excluir `data/` del deploy), para no dejar en la web un GeoJSON más viejo que el del cron.

### Obtener el GeoJSON para incluirlo en el frontend

La fuente canónica del dato es **la producción** (la salida del cron). Para llevarla al repo del frontend, en la raíz del clon de GadirE:

```bash
curl -o data/map_data.geojson https://gadire.alfeva.net/data/map_data.geojson
```

(o copiarla directamente del servidor: `scp <usuario>@<servidor>:generador_geojson_gadire/map_data.geojson data/`)

Verificación rápida antes de commitear:
```bash
python3 -c "import json; d=json.load(open('data/map_data.geojson')); fs=d['features']; print(len(fs), 'features'); assert len({f['properties']['idnum'] for f in fs})==len(fs); assert all(f['properties']['campus'] and f['properties']['campus']!='Desconocido' for f in fs); print('OK')"
```

Tras cambiar el GeoJSON, recordar el **bump de la caché del service worker** (`CACHE_NAME` en `sw.js`) para que los clientes lo refresquen.

---

## 🔍 Casos de Uso

### 🆕 Crear el GeoJSON desde cero
1. Colocar `map_data_form.csv` en la carpeta.
2. Ejecutar `adecuacion.py` → genera `map_data.csv`.
3. Ejecutar `generador_map_data.py` → genera `map_data.geojson` y `log.json`.

### 🔄 Actualizar el GeoJSON existente
1. Añadir nuevas filas a `map_data_form.csv`.
2. Ejecutar `adecuacion.py` → actualiza `map_data.csv`.
3. Ejecutar `generador_map_data.py` → actualiza `map_data.geojson` y `log.json` (sin duplicar lugares ya procesados).

---

## ⚠️ Limitaciones y Consideraciones

1. **Inferencia geográfica**:
   - La precisión depende de la calidad de los polígonos en los KML.
   - Los lugares fuera de todo polígono se excluyen del GeoJSON (pero quedan como procesados).

2. **Modelo de lenguaje (Ollama)**:
   - La clasificación y revisión dependen del modelo. Puede requerir ajustes en el prompt para mejorar la precisión (los falsos positivos existen: ver "Validación manual").
   - Si el modelo devuelve un tipo no predefinido, se corrige automáticamente.

3. **IDs únicos**:
   - El sistema garantiza IDs únicos dentro de un mismo (campus, edificio, planta, tipo).
   - No se garantiza unicidad global si se modifican manualmente los archivos de estado; ante la duda, regenerar.

4. **Rendimiento**:
   - Procesar muchos lugares puede ser lento debido a las llamadas al modelo de lenguaje (solo se revisa lo nuevo, así que el coste es incremental).

---

## 📚 Ejemplo Práctico (Universidad de Cádiz)

### Entrada (`map_data_form.csv`)
   Nombre del lugar       | Descripción          | Planta | Coordenadas: latitud | Coordenadas: longitud |
 |------------------------|----------------------|--------|----------------------|-----------------------|
 | Aula 1.2               | Aula de informática  | 1      | 36.543210            | -6.234567             |
 | Cafetería Central      | Cafetería principal  | Baja   | 36.541234            | -6.236543             |

### Salida (`map_data.geojson`)
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "nombre": "Aula 1.2",
        "tipo": "aula",
        "planta": "1",
        "edificio": "Facultad de Ciencias",
        "campus": "Puerto Real",
        "idnum": "330010301"
      },
      "geometry": {
        "type": "Point",
        "coordinates": [-6.234567, 36.543210]
      }
    }
  ]
}
```
**Nota**: Si un lugar queda con `campus` o `edificio` sin asignar (`None`) o `"Desconocido"`, **no se incluirá en el GeoJSON**.

---

## 🛑 Solución de Problemas
 | Problema | Posible Causa | Solución |
 |---|---|---|
 | Error al cargar KML | Archivo KML mal formado o inexistente. | Verificar que los KML existan y tengan polígonos con atributo `Name`. |
 | Ollama no responde | Servicio no iniciado o modelo no descargado. | Ejecutar `ollama serve` y descargar el modelo (`ollama pull mistral:7b`). |
 | `ModuleNotFoundError` en el servidor | El venv no está activado. | Activar el venv antes de ejecutar los scripts. |
 | IDs duplicados | `log.json` corrupto o editado a mano. | **Regenerar**: borrar `log.json` y `map_data.geojson` **juntos** y ejecutar de nuevo. |
 | GeoJSON vacío (0 features) | Se borró `map_data.geojson` pero no `log.json`. | Borrar **ambos** archivos y ejecutar de nuevo. |
 | Features duplicadas o fantasma | Se borró `log.json` pero no el `map_data.geojson` viejo. | Borrar **ambos** archivos y ejecutar de nuevo (la regeneración los purga). |
 | Un lugar aprobado nunca aparece | Se aprobó a mano una fila con índice ≤ `ultima_fila_procesada`. | Regenerar (ver la trampa de `ultima_fila`). |
 | Lugares sin campus/edificio en el GeoJSON | Coordenadas fuera de los polígonos. | Revisar los KML o añadir polígonos; el lugar queda excluido por diseño. |
 | `rm` no borra `log.json`/`map_data.geojson` en el servidor | Son de root (los crea el cron) y `rm` pregunta. | Usar `sudo rm -f` (el `rm` interactivo, por defecto, NO borra). |
 | `Error opening terminal: xterm-kitty` en nano/git | El servidor no tiene el terminfo de kitty. | `export TERM=xterm` antes de usar nano o git por SSH. |

---

## 📌 Notas Finales

- **Extensibilidad**: El sistema está diseñado para adaptarse a otras universidades modificando los códigos y los KML.
- **Automatización**: En producción se ejecuta con cron (mapa de lunes a viernes, calendario a diario), siempre con descarga atómica de entradas y publicación segura de salidas.
- **Validación manual**: Siempre revisar los lugares marcados como `"Revisar manualmente"` en `map_data.csv` y **regenerar** después de editar filas a mano.
- **Sincronización `.ipynb`/`.py`**: Todo cambio al código debe reflejarse en el cuaderno y en su exporte a Python.
- **Generación de KML**: Se recomienda usar [Google My Maps](https://www.google.com/maps/about/mymaps/) para crear los polígonos de campus y edificios.