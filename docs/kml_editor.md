# Editor de KML (campus y edificios)

Este documento describe `editor_kml.html`, el editor visual de los dos archivos KML que alimentan al generador (`generador_map_data.py`): `campus.kml` y `edificios.kml`.

## Qué es

Una página HTML única, sin instalación ni servidor: se abre con cualquier navegador moderno y permite dibujar, editar, renombrar, reordenar, importar y exportar los polígonos de campus y edificios directamente en el formato exacto que lee el generador.

- **Bibliotecas por CDN** (Leaflet 1.9.4, Leaflet-Geoman free 2.20.0 y Turf.js 7.2.0, con hashes de integridad SRI) y mapa de OpenStreetMap: necesita conexión a internet. Cuando el proyecto pase a ser multiarchivo, las bibliotecas se vendorizarán en el propio archivo.
- **Autoguardado en el navegador** (`localStorage`): el trabajo no se pierde al cerrar la pestaña, pero es local a cada navegador y equipo. La copia buena es siempre la descargada: tras cada sesión de edición, descárguense los KML y confírmense al repositorio.
- Deshacer/rehacer: `Ctrl/Cmd+Z` y `Ctrl/Cmd+Shift+Z` (hasta 50 pasos).

## Uso

### Dibujar

1. El selector **Draw to** (arriba a la derecha) decide si el próximo polígono va a *Buildings* (`edificios.kml`) o a *Campuses* (`campus.kml`).
2. Actívese el botón de polígono de la barra de herramientas y cliquéense los vértices sobre el mapa.
3. La figura se termina haciendo clic sobre el primer vértice o pulsando `Enter`; `Escape` sale del modo de dibujo.
4. **Imán (snapping)**: los clics se pegan a vértices y aristas existentes (radio de 20 px). El botón del imán en la barra lo activa o desactiva, y mantener `Alt` lo ignora momentáneamente.
5. El primer vértice de una figura nueva se fija exactamente sobre el vértice de otro polígono si está cerca (mismo radio de 20 px), de modo que los edificios colindantes compartan esquinas con precisión.

### Reglas de validación

- **Anillos simples**: el contorno de un polígono no puede cruzarse a sí mismo (nada de "caramelos de cuatro vértices"). Geoman lo bloquea en vivo mientras se dibuja; no hace falta ser convexo (las formas en L o similares son válidas).
- **Sin solapes dentro de una misma capa**: dos edificios (o dos campus) solapados quedan marcados con el distintivo *Overlapping* y con contorno discontinuo. No se bloquea la descarga, pero se avisa. Un edificio dentro de un campus es la situación esperada.
- **Nombres únicos**: los duplicados quedan marcados (*Duplicate name*); el generador empareja los KML por nombre exacto, así que dos polígonos con el mismo nombre son un error.
- El botón de descarga resume los problemas encontrados y pide confirmación, pero la decisión final es del usuario.

### La barra lateral

- **Import**: carga un `campus.kml` o `edificios.kml` existente en la capa correspondiente (los Placemarks con varios polígonos se separan en una entrada por polígono).
- Cada polígono muestra su **código**, que se deriva de su posición en la lista (edificios: `"01"`, `"02"`, …; campus: `"0"`, `"1"`, …) y su **nombre**, editable.
- **Reordenar**: arrastrando el asa `⠿` se cambia la posición de un polígono y se renumeran todos los códigos (funciona también en pantallas táctiles).
- Pasar el cursor por un polígono del mapa muestra su nombre; hacer clic sobre él destaca su fila en la lista (y al revés: el cursor sobre una fila engorda el contorno del polígono).
- **Zoom** (`⌖`) y **borrar** (`✕`) por elemento.
- **Copy Python codes**: copia al portapapeles los diccionarios `edificio_codes`/`campus_codes` correspondientes al orden actual de las listas.
- **Download**: exporta `edificios.kml` o `campus.kml` listos para sustituir a los del repositorio.

### El control "View"

Arriba a la derecha del mapa, las casillas **View** muestran u ocultan cada capa. No puede dibujarse en una capa oculta: si se intenta, se explica cómo reactivarla; si se oculta la capa activa mientras se dibuja, el modo de dibujo se detiene en silencio.

## Compatibilidad con el generador (formato de salida)

Los KML exportados son un reemplazo directo de los actuales:

- Nombres de archivo: `campus.kml` y `edificios.kml`; nombres de documento: `Campus` y `Edificios`.
- Un `<Placemark>` por polígono, con estructura idéntica a una exportación de Google My Maps (`StyleMap`, `tessellate`, anillos cerrados) y coordenadas redondeadas a **6 decimales** (≈11 cm).
- El generador los lee con `gpd.read_file(driver='KML')` y empareja el `<name>` de cada polígono con las claves de `campus_codes`/`edificio_codes` **mediante coincidencia exacta**, e infiere campus y edificio con `Point.within(polygon)`.

Dos consecuencias prácticas de esa lectura:

- **Un punto justo en el borde puede no inferirse**: `within` exige el interior estricto del polígono. Si un aporte cae exactamente sobre una arista (p. ej., sobre una pared compartida), puede quedar sin campus o edificio y excluirse del GeoJSON.
- **Con polígonos solapados gana el primero que contenga al punto**: para campus se recorren en orden; para edificios solo se buscan los del campus inferido. Evítense los solapes (el propio editor los marca).

## Flujo de trabajo recomendado (actualizar los polígonos)

1. Ábrase `editor_kml.html` y **Import** los KML actuales (la importación conserva el orden del archivo).
2. Edítense los polígonos: mover vértices, renombrar, añadir, eliminar, reordenar.
3. **Download** los dos archivos y sustitúyanse en la carpeta del repositorio.
4. Si se han añadido edificios o campus nuevos, actualícense también `generador_map_data.py`:
   - Cada **edificio nuevo** necesita (a) entrada en `edificio_codes` con el código siguiente, y (b) entrada en su conjunto de campus (`campusBahiaAlgeciras`, `campusCadiz`, `campusJerez` o `campusPuertoReal`). Sin ambas, el generador no llegará a inferirlo y sus lugares quedarán excluidos.
   - Cada **campus nuevo** necesita entrada en `campus_codes` (y su conjunto de edificios).
   - Si se ha **renombrado** algo, actualícense igualmente las claves de `edificio_codes`/`campus_codes` y los conjuntos.
   - El botón **Copy Python codes** del editor genera los diccionarios ya renumerados según el orden actual de las listas, listos para pegar.
5. **Regenerar**: el incremental solo publica las filas nuevas; para que TODAS las features se reubiquen con los polígonos nuevos, bórranse juntos `log.json` y `map_data.geojson` y ejecútese de nuevo (ver la sección de regeneración de `docs/gen_GeoJSON.md`).
6. Si se ha **eliminado** un edificio, téngase en cuenta que sus lugares dejarán de inferirse: la regeneración los retirará del mapa (quedan como filas excluidas del CSV, no se pierden).

## Limitaciones

- Requiere conexión a internet (bibliotecas por CDN y teselas del mapa).
- El autoguardado es local al navegador; los KML del repositorio son la fuente de verdad.
- El editor trabaja con polígonos simples (un anillo exterior por Placemark); no soporta agujeros (`innerBoundaryIs`) ni importa GeoJSON (pendiente).
- Los códigos se derivan del orden de la lista: si se reordena y se copian los diccionarios generados, cambian los códigos `EE` de los `idnum` existentes. Es inocuo si después se regenera el GeoJSON completo, pero conviene importar los KML en su orden original para no renumerar por accidente.