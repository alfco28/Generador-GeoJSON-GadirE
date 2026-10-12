# Generador del GeoJSON

Este proyecto tiene por finalidad facilitar el generar desde cero y actualizar el archivo GeoJSON que contiene los datos del mapa usado en el proyecto *GadirE*.

## Entrada

Al ejecutarse, tomará tres archivos:

### `map_data.csv`

Necesario. Deberá tener estas columnas:

- `Nombre del lugar`.
- `Descripción`.
- `Enlace`.
- `Edificio o Centro`.
- `Planta`.
- `Tipo`.
- `Coordenadas: latitud`.
- `Coordenadas: longitud`.

Si en algún elemento alguna de estas columnas está vacía, se establecerá la cadena vacía como resultado para la columna y elemento correspondiente.

Está pensado para que se obtenga a partir de un formulario que rellenen los usuarios, reportando así la falta de lugares en el mapa.

### `map_data.geojson`

Opcional. Si es dado, se actualizará añadiendo los puntos del mapa nuevos que aparezcan en `map_data.csv`, i.e., los que no estaban ya de antes de acuerdo con `log.json`.

### `log.json`

Opcional. No está pensado para ser creado manualmente, sino por este mismo programa. Lleva un registro de la última línea del CSV que se añadió en el GeoJSON, así como de los índices de cada (tipo, planta, edificio, campus).

## Salida

### `map_data.geojson`

Archivo con los datos del mapa, compatible con el sistema de funcionamiento de *GadirE*. Listo para ser incluido en la carpeta `data` de *GadirE*.

### `log.json`

Archivo que lleva un registro de los lugares que ya se han incluido anteriormente en `map_data.geojson`.

## Funcionamiento externo

Está pensado para que se incluya en una carpeta el archivo principal del proyecto (`generador_map_data.ipynb`) y `map_data.csv`.

- Si se necesita crear por primera vez el archivo `map_data.geojson`, ejecútese el cuaderno `generador_map_data.ipynb` al completo y por orden. Se crearán en la carpeta los archivos `map_data.geojson` y `log.json`.
- Si se necesita actualizar el archivo `map_data.geojson`, ejecútese el cuaderno `generador_map_data.ipynb` al completo y por orden. Se sobreescribirán los archivos `map_data.geojson` y `log.json`.
  Téngase en cuenta que al actulizar el archivo `map_data.geojson`, este programa no realiza ninguna acción sobre su contenido inicial más que copiarlo para conservarlo en el futuro `map_data.geojson`.

Déjense estos cuatro archivos en la misma carpeta siempre, y cópiese `map_data.geojson` en la carpeta `data` de *GadirE*.

### Comportamientos inesperados

No se hagan combinaciones diferentes a las mencionadas en cuanto a la existencia o no de los mencionados archivos, podría resultar en comportamientos inesperados, pérdida de información en el archivo `map_data.geojson` o información errónea en `map_data.geojson` y/o `log.json`.

Dado el caso, siempre se puede volver a empezar de nuevo todo el proceso dejando únicamente los archivos `generador_map_data.ipynb` y `map_data.csv` y eliminando `map_data.geojson` y `log.json`.

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

Considérense las limitaciones que puedan implicar este sistema numeración.

Este sistema de numeración es el que usa *GadirE* para determinar y distinguir los *features*. Es indispensable que `map_data.geojson` no contenga dos *features* con el mismo `idnum`, este programa cumple con esa condición dentro de sus límites.