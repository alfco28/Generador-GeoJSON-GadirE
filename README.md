# Documentación del Sistema de Generación de GeoJSON para mapas universitarios

---

## 📌 Introducción

Este proyecto permite **generar y actualizar** un archivo **GeoJSON** con datos georreferenciados de lugares en un campus universitario, diseñado para ser compatible con sistemas como *GadirE*. El proceso se divide en dos scripts principales:

1. **`adecuacion.py`**: Procesa un CSV de entrada, revisa y clasifica los lugares usando un modelo de lenguaje (Ollama), y genera un CSV intermedio con los datos validados y clasificados.
2. **`generador_map_data.py`**: Toma el CSV procesado, infiere campus y edificios a partir de coordenadas, y genera el GeoJSON final con identificadores únicos, **excluyendo lugares con campus o edificio "Desconocido"**.

---

## 📂 Estructura del Proyecto

```
├── adecuacion.py          # Script de preprocesamiento y clasificación
├── generador_map_data.py  # Script de generación del GeoJSON
├── campus.kml             # Polígonos de los campus (para inferencia geográfica)
├── edificios.kml          # Polígonos de los edificios (para inferencia geográfica)
├── map_data_form.csv      # CSV de entrada con lugares reportados por usuarios
├── map_data.csv           # CSV intermedio (generado por adecuacion.py)
└── map_data.geojson       # GeoJSON final (generado por generador_map_data.py)
```

---

## 🔄 Flujo de Trabajo

### 1. Preprocesamiento (`adecuacion.py`)
- **Entrada**: `map_data_form.csv` (lugares reportados por usuarios).
- **Salida**: `map_data.csv` (lugares validados, clasificados y con tipo corregido).
- **Proceso**:
  - Revisa cada fila para determinar si el contenido es adecuado (usando Ollama).
  - Clasifica el tipo de lugar (ej: "Aula", "Cafetería").
  - Corrige el tipo para que coincida exactamente con los predefinidos.
  - Guarda el resultado en `map_data.csv` con columnas adicionales: `Revisado`, `Aprobado`, `Tipo`.

### 2. Generación del GeoJSON (`generador_map_data.py`)
- **Entrada**:
  - `map_data.csv` (lugares validados).
  - `campus.kml` y `edificios.kml` (para inferir campus/edificio a partir de coordenadas).
  - `log.json` (opcional, para continuar desde la última ejecución).
- **Salida**:
  - `map_data.geojson` (GeoJSON con todos los lugares **excluyendo aquellos con campus o edificio "Desconocido"**).
  - `log.json` (registro de progreso y contadores de IDs).
- **Proceso**:
  - Infiere el campus y edificio de cada lugar usando los KML.
  - **Excluye lugares con campus o edificio "Desconocido"**.
  - Genera un `idnum` único para cada lugar.
  - Combina los nuevos lugares con los existentes (si `map_data.geojson` ya existe).
  - Ordena y guarda el GeoJSON final.

---

## 📝 Especificaciones de Entrada/Salida

### Entradas

#### `map_data_form.csv`
**Columnas obligatorias**:
- `Nombre del lugar`: Nombre del lugar (ej: "Aula 1.2").
- `Descripción`: Descripción opcional.
- `Enlace`: URL opcional (ej: enlace a más información).
- `Planta`: Planta donde se ubica (ej: "Baja", "1").
- `Coordenadas: latitud`: Latitud del lugar.
- `Coordenadas: longitud`: Longitud del lugar.

**Notas**:
- Si falta alguna columna, se asumirá un valor vacío.
- Este CSV puede generarse a partir de un formulario de usuarios.

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
        "idnum": "328010301"  # Ejemplo de ID único
      },
      "geometry": {
        "type": "Point",
        "coordinates": [-6.234567, 36.543210]
      }
    }
  ]
}
```
**Nota**: Solo se incluyen lugares con `campus` y `edificio` distintos de `"Desconocido"`.

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
- Si un lugar no está dentro de ningún polígono, se marcará como `"Desconocido"` y **se excluirá del GeoJSON**.

---

## 🛠️ Requisitos y Dependencias

### Python
- Versión utilizada: **3.9.6** (compatible con 3.8+).

### Librerías
Instalar con:
```bash
pip install pandas ollama Levenshtein unidecode geopandas shapely
```

### Ollama
- Requiere un modelo de Ollama local (ej: `mistral-small3.2:latest`).
- **Enlaces útiles**:
  - [Ollama GitHub](https://github.com/jmorganca/ollama)
  - [Documentación de Ollama](https://github.com/jmorganca/ollama#readme)
  - Descargar el modelo: `ollama pull mistral-small3.2:latest`
- Asegurarse de que el servicio de Ollama esté en ejecución:
  ```bash
  ollama serve
  ```

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
   - Lugares fuera de polígonos se marcarán como `"Desconocido"` y **se excluirán del GeoJSON**.

2. **Modelo de lenguaje (Ollama)**:
   - La clasificación y revisión dependen del modelo. Puede requerir ajustes en el prompt para mejorar la precisión.
   - Si el modelo devuelve un tipo no predefinido, se corrige automáticamente.

3. **IDs únicos**:
   - El sistema garantiza IDs únicos dentro de un mismo (campus, edificio, planta, tipo).
   - No se garantiza unicidad global si se modifican manualmente los archivos.

4. **Rendimiento**:
   - Procesar muchos lugares puede ser lento debido a las llamadas al modelo de lenguaje.

---

## 📚 Ejemplo Práctico (Universidad de Cádiz)

### Entrada (`map_data_form.csv`)
| Nombre del lugar       | Descripción          | Planta | Coordenadas: latitud | Coordenadas: longitud |
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
**Nota**: Si un lugar tiene `campus: "Desconocido"` o `edificio: "Desconocido"`, **no se incluirá en el GeoJSON**.

---

## 🛑 Solución de Problemas

| Problema                          | Posible Causa                          | Solución                                                                 |
|-----------------------------------|----------------------------------------|--------------------------------------------------------------------------|
| Error al cargar KML               | Archivo KML mal formado o inexistente. | Verificar que los KML existan y tengan polígonos con atributo `Name`.   |
| Ollama no responde                | Servicio no iniciado o modelo no descargado. | Ejecutar `ollama serve` y descargar el modelo (`ollama pull mistral-small3.2:latest`). |
| IDs duplicados                    | `log.json` corrupto o modificado manualmente. | Eliminar `log.json` y volver a ejecutar desde cero.                   |
| Lugares no asignados a campus/edificio | Coordenadas fuera de polígonos.   | Revisar los KML o añadir polígonos faltantes.                          |
| Lugares "Desconocido" en el GeoJSON | Error en la lógica de exclusión.      | Verificar que el `if` de exclusión esté correctamente implementado.   |

---

## 📌 Notas Finales

- **Extensibilidad**: El sistema está diseñado para adaptarse a otras universidades modificando los códigos y los KML.
- **Automatización**: Puede integrarse en un flujo automatizado (ej: ejecución periódica con nuevos datos de `map_data_form.csv`).
- **Validación manual**: Siempre revisar los lugares marcados como `"Revisar manualmente"` en `map_data.csv`.
- **Generación de KML**: Se recomienda usar [Google My Maps](https://www.google.com/maps/about/mymaps/) para crear los polígonos de campus y edificios.