# %%
# Importar las librerías necesarias
import csv
import json
import os
from collections import defaultdict
from datetime import datetime
import geopandas as gpd
from shapely.geometry import Point

import dedup

# %%
#Definición de edificios que conforman cada campus para posterior inferencia del campus a partir del edificio

campusBahiaAlgeciras = {
    "Biblioteca del Campus Bahía de Algeciras",
    "Centro de Innovación UCA-SEA",
    "Edificio I+D+i",
    "Escuela Técnica Superior de Ingeniería de Algeciras (ETSIA)",
    "Facultad de Enfermería (Algeciras)"
}

campusCadiz = {
    "Colegio Mayor",
    "Edificio Andrés Segovia",
    "Edificio Constitución de 1812 (la Bomba)",
    "Edificio El Olivillo (Centro de Transferencia Empresarial)",
    "Edificio ESI-1 (Cádiz)",
    "Edificio Hospital Real",
    "Edificio José Pedro Pérez-Llorca",
    "Edificio Multiusos del Campus de Cádiz",
    "Edificio Reina Sofía",
    "Edificio Simón Bolívar (Casa del Estudiante)",
    "Edificio Valcárcel",
    "Facultad de Ciencias del Trabajo",
    "Facultad de Ciencias Económicas y Empresariales",
    "Facultad de Enfermería y Fisioterapia",
    "Facultad de Filosofía y Letras",
    "Facultad de Medicina",
    "LABIMAR"
}

campusJerez = {
    "Aulario Carmelo García Barroso",
    "Aulario del Campus de Jerez",
    "Biblioteca del Campus de Jerez",
    "Edificio de Despachos y Seminarios del Campus de Jerez",
    "Edificio de Servicios Comunes del Campus de Jerez",
    "Edificio Multiusos del Campus de Jerez",
    "Instituto Universitario de Investigación para el Desarrollo Social Sostenible (INDESS)",
    "Piscina del Campus de Jerez",
    "Pistas desportivas del Campus de Jerez"
}

campusPuertoReal = {
    "Aulario Norte del Campus de Puerto Real",
    "Aulario Sur del Campus de Puerto Real",
    "Biblioteca del Campus de Puerto Real",
    "Centro Andaluz Superior de Estudios Marinos (CASEM)",
    "Centro Integrado de Tecnologías de la Información (CITI)",
    "Complejo Deportivo del Campus de Puerto Real",
    "Escuela Infantil La Algaida",
    "Escuela Superior de Ingeniería (ESI)",
    "Facultad de Ciencias",
    "Facultad de Ciencias de la Educación",
    "Instituto de Ciencias Marinas de Andalucía",
    "Institutos de Investigación INMAR/IVAGRO",
    "Registro del Campus de Puerto Real"
}


# %%
# Definir los códigos predefinidos para campus, edificios, plantas y tipos
campus_codes = {
    "Bahía de Algeciras": "2",
    "Cádiz": "0",
    "Jerez": "1",
    "Puerto Real": "3"
}

edificio_codes = {
    "Aulario Carmelo García Barroso": "01",
    "Aulario del Campus de Jerez": "02",
    "Aulario Norte del Campus de Puerto Real": "03",
    "Aulario Sur del Campus de Puerto Real": "04",
    "Biblioteca del Campus Bahía de Algeciras": "05",
    "Biblioteca del Campus de Jerez": "06",
    "Biblioteca del Campus de Puerto Real": "07",
    "Centro Andaluz Superior de Estudios Marinos (CASEM)": "08",
    "Centro de Innovación UCA-SEA": "09",
    "Centro Integrado de Tecnologías de la Información (CITI)": "10",
    "Colegio Mayor": "11",
    "Complejo Deportivo del Campus de Puerto Real": "12",
    "Edificio Andrés Segovia": "13",
    "Edificio Constitución de 1812 (la Bomba)": "14",
    "Edificio de Despachos y Seminarios del Campus de Jerez": "15",
    "Edificio de Servicios Comunes del Campus de Jerez": "16",
    "Edificio El Olivillo (Centro de Transferencia Empresarial)": "17",
    "Edificio ESI-1 (Cádiz)": "18",
    "Edificio Hospital Real": "19",
    "Edificio I+D+i": "20",
    "Edificio José Pedro Pérez-Llorca": "21",
    "Edificio Multiusos del Campus de Cádiz": "22",
    "Edificio Multiusos del Campus de Jerez": "23",
    "Edificio Reina Sofía": "24",
    "Edificio Simón Bolívar (Casa del Estudiante)": "25",
    "Edificio Valcárcel": "26",
    "Escuela Infantil La Algaida": "27",
    "Escuela Superior de Ingeniería (ESI)": "28",
    "Escuela Técnica Superior de Ingeniería de Algeciras (ETSIA)": "29",
    "Facultad de Ciencias": "30",
    "Facultad de Ciencias de la Educación": "31",
    "Facultad de Ciencias del Trabajo": "32",
    "Facultad de Ciencias Económicas y Empresariales": "33",
    "Facultad de Enfermería (Algeciras)": "34",
    "Facultad de Enfermería y Fisioterapia": "35",
    "Facultad de Filosofía y Letras": "36",
    "Facultad de Medicina": "37",
    "Instituto de Ciencias Marinas de Andalucía": "38",
    "Institutos de Investigación INMAR/IVAGRO": "39",
    "Instituto Universitario de Investigación para el Desarrollo Social Sostenible (INDESS)": "40",
    "LABIMAR": "41",
    "Piscina del Campus de Jerez": "42",
    "Pistas desportivas del Campus de Jerez": "43",
    "Registro del Campus de Puerto Real": "44"
}

planta_codes = {
    "Sótano": "11",
    "Baja": "10",
    "1": "01",
    "2": "02",
    "3": "03",
    "4": "04",
    "5": "05",
    "6": "06",
    "7": "07"
}

# Códigos numéricos para tipos (para idnum)
tipo_codes_num = {
    "Área de descanso": "01",
    "Aseo o vestuario": "02",
    "Aula": "03",
    "Biblioteca o sala de estudio": "04",
    "Cafetería, fuente o máquina": "05",
    "Despacho": "06",
    "Laboratorio o taller": "07",
    "Representación de estudiantes": "08",
    "Salida de emergencia o punto de encuentro": "09",
    "Salón de Actos o de Grado": "10",
    "Transporte": "11",
    "Unidades o servicios": "12"
}

# Cadenas de texto para tipos (para propiedades)
tipo_codes_str = {
    "Área de descanso": "descanso",
    "Aseo o vestuario": "aseo",
    "Biblioteca o sala de estudio": "biblio",
    "Cafetería, fuente o máquina": "cafete",
    "Despacho": "despacho",
    "Laboratorio o taller": "lab",
    "Representación de estudiantes": "repre",
    "Salida de emergencia o punto de encuentro": "emergencia",
    "Salón de Actos o de Grado": "salon",
    "Transporte": "transporte",
    "Unidades o servicios": "unidad"
}

# %%
def redondear_coordenadas(coord):
    """Redondea una coordenada a 6 decimales si tiene más."""
    try:
        coord_float = float(coord)
        return round(coord_float, 6)
    except ValueError:
        return coord

# %%
# FIX 24-10: el incremental pasa de posicional ("ultima_fila_procesada") a por
# Timestamp. El bug: las respuestas nuevas del formulario entran ARRIBA del
# sheet, así que las filas viejas se desplazan de posición y el índice
# posicional vuelve a procesarlas (duplicando features), mientras que las
# filas nuevas (índices pequeños) nunca se procesaban. El Timestamp es la
# clave única de cada aporte (la misma con la que adequacion.py deduplica),
# así que el incremental por Timestamp es inmune a cualquier reordenación.
def cargar_log(ruta_log):
    try:
        with open(ruta_log, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Sin log (o corrupto): lista de procesados vacía; se entiende que
        # también se ha borrado map_data.geojson para regenerar de cero
        return {"procesados": [], "id_counter": {}}

def guardar_log(ruta_log, procesados, id_counter, fusiones=None, avisos=None):
    # Convertir defaultdict a dict normal para guardar en JSON
    id_counter_dict = {}
    for campus, edificios in id_counter.items():
        id_counter_dict[campus] = {}
        for edificio, plantas in edificios.items():
            id_counter_dict[campus][edificio] = {}
            for planta, tipos in plantas.items():
                id_counter_dict[campus][edificio][planta] = {}
                for tipo, contador in tipos.items():
                    id_counter_dict[campus][edificio][planta][tipo] = int(contador)

    with open(ruta_log, 'w', encoding='utf-8') as f:
        json.dump({
            "procesados": sorted(procesados),
            "id_counter": id_counter_dict,
            # Auditoría de la deduplicación: fusiones realizadas y avisos de
            # posibles duplicados NO fusionados (por distancia). Claves nuevas,
            # compatibles hacia atrás (los logs antiguos no las traen)
            "fusiones": fusiones or [],
            "avisos_duplicados": avisos or []
        }, f, indent=4)

# %%
def cargar_kml_a_geodataframe(ruta_kml):
    """
    Carga un archivo KML como GeoDataFrame de geopandas.

    Args:
        ruta_kml (str): Ruta al archivo KML.

    Returns:
        gpd.GeoDataFrame: GeoDataFrame con los polígonos del KML.
    """
    return gpd.read_file(ruta_kml, driver='KML')

# %%
def inferir_campus(lat, lon, gdf_campus):
    """
    Infiere el campus al que pertenece un punto (lat, lon) usando los polígonos del KML de campus.

    Args:
        lat (float): Latitud del punto.
        lon (float): Longitud del punto.
        gdf_campus (gpd.GeoDataFrame): GeoDataFrame con los polígonos de los campus.

    Returns:
        str: Nombre del campus o None si no está en ningún polígono.
    """
    punto = Point(lon, lat)
    for _, row in gdf_campus.iterrows():
        if punto.within(row.geometry):
            return row['Name']  # Asegúrate de que la columna con el nombre del campus se llame 'Name'
    return None

def inferir_edificio(lat, lon, gdf_edificios, campus=None):
    """
    Infiere el edificio al que pertenece un punto (lat, lon).
    Si se especifica un campus, solo busca en los edificios de ese campus.

    Args:
        lat (float): Latitud del punto.
        lon (float): Longitud del punto.
        gdf_edificios (gpd.GeoDataFrame): GeoDataFrame con los polígonos de los edificios.
        campus (str, optional): Nombre del campus para filtrar edificios.

    Returns:
        str: Nombre del edificio o None si no está en ningún polígono.
    """
    punto = Point(lon, lat)
    if campus:
        # Filtrar edificios según el campus (usando tus listas)
        edificios_filtrados = []
        if campus == "Bahía de Algeciras":
            edificios_filtrados = [edificio for edificio in campusBahiaAlgeciras if edificio in gdf_edificios['Name'].values]
        elif campus == "Cádiz":
            edificios_filtrados = [edificio for edificio in campusCadiz if edificio in gdf_edificios['Name'].values]
        elif campus == "Jerez":
            edificios_filtrados = [edificio for edificio in campusJerez if edificio in gdf_edificios['Name'].values]
        elif campus == "Puerto Real":
            edificios_filtrados = [edificio for edificio in campusPuertoReal if edificio in gdf_edificios['Name'].values]
        # Filtrar el GeoDataFrame
        gdf_edificios = gdf_edificios[gdf_edificios['Name'].isin(edificios_filtrados)]

    for _, row in gdf_edificios.iterrows():
        if punto.within(row.geometry):
            return row['Name']
    return None

# %%
def leer_csv_y_generar_json(ruta_csv, ruta_kml_campus="campus.kml", ruta_kml_edificios="edificios.kml", ruta_geojson="map_data.geojson", ruta_log="log.json"):
    """
    Lee un CSV con puntos, infiere el campus y edificio a partir de las coordenadas,
    y genera un GeoJSON con los datos procesados.

    Args:
        ruta_csv (str): Ruta al archivo CSV con los puntos.
        ruta_kml_campus (str): Ruta al KML con los polígonos de los campus.
        ruta_kml_edificios (str): Ruta al KML con los polígonos de los edificios.
        ruta_geojson (str): Ruta al GeoJSON de salida.
        ruta_log (str): Ruta al archivo de log.

    Returns:
        dict: FeatureCollection con los puntos procesados.
    """
    # Cargar los KML como GeoDataFrames
    gdf_campus = cargar_kml_a_geodataframe(ruta_kml_campus)
    gdf_edificios = cargar_kml_a_geodataframe(ruta_kml_edificios)

    # Cargar el log
    log = cargar_log(ruta_log)
    # FIX 24-10: si el log tiene el formato antiguo (posicional) no hay forma
    # de saber qué filas ya están publicadas; seguir aquí duplicaría todo el
    # mapa. Se aborta pidiendo la regeneración (borrar log.json y
    # map_data.geojson JUNTOS, como siempre) en lugar de corromper el mapa.
    if "procesados" not in log:
        raise SystemExit("log.json con formato antiguo: borra log.json y map_data.geojson (juntos) y vuelve a ejecutar.")
    # Timestamps de los aportes que ya tienen su feature publicado
    procesados = set(log.get("procesados", []))
    # Auditoría de la deduplicación (claves nuevas: los logs sin ellas dan [])
    fusiones = list(log.get("fusiones", []))
    avisos_duplicados = list(log.get("avisos_duplicados", []))
    id_counter = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))

    # Cargar el contador de IDs desde el log
    for campus, edificios in log["id_counter"].items():
        for edificio, plantas in edificios.items():
            for planta, tipos in plantas.items():
                for tipo, contador in tipos.items():
                    id_counter[campus][edificio][planta][tipo] = contador

    # Cargar el GeoJSON existente (si existe)
    features_antiguos = []
    if os.path.exists(ruta_geojson):
        with open(ruta_geojson, 'r', encoding='utf-8') as f:
            geojson_existente = json.load(f)
            features_antiguos = geojson_existente.get("features", [])

    # Índices para la deduplicación: por grupo (campus, edificio, planta), por
    # idnum (marcas "Duplicado de" de features publicadas) y por Timestamp (marcas
    # de gemelos creados en esta misma ejecución). Las fusiones mutan las
    # features in situ, así que los índices siempre ven el estado actualizado.
    features_por_grupo = {}
    features_por_idnum = {}
    features_por_timestamp = {}
    for feature in features_antiguos:
        props = feature.get("properties", {})
        grupo = (props.get("campus"), props.get("edificio"), dedup.normalizar_planta(props.get("planta")))
        features_por_grupo.setdefault(grupo, []).append(feature)
        if props.get("idnum"):
            features_por_idnum[props["idnum"]] = feature

    # Procesar las filas del CSV cuyo Timestamp no esté publicado aún.
    # Las no aprobadas no se marcan como procesadas: se reexaminan en cada
    # ejecución (es barato, aquí no hay LLM), de modo que si Alfonso aprueba
    # a mano una fila "Revisar manualmente" (o cambia un "No" por un "Sí"),
    # el próximo run la publica sin más (adiós a la trampa de ultima_fila).
    features_nuevos = []
    with open(ruta_csv, mode='r', encoding='utf-8') as archivo_csv:
        lector_csv = csv.DictReader(archivo_csv)
        filas = list(lector_csv)

    # Orden cronológico por Timestamp (dd/mm/aaaa hh:mm:ss): la feature "base"
    # de cada lugar es su primer reporte y las duplicadas se fusionan sobre
    # ella en orden natural. También hace que la regeneración completa
    # produzca lo mismo que el incremental haya ido publicando.
    def clave_cronologica(fila):
        """Clave de orden: el Timestamp parseado; al final si no se puede parsear."""
        try:
            return (0, datetime.strptime(fila.get("Timestamp", "").strip(), "%d/%m/%Y %H:%M:%S"))
        except ValueError:
            return (1, datetime.min)  # formato desconocido: conserva el orden relativo

    filas = sorted(filas, key=clave_cronologica)

    for fila in filas:
        # Clave única del aporte: el Timestamp del formulario
        timestamp = fila.get("Timestamp", "").strip()

        # Saltar los aportes que ya tienen su feature publicado
        if timestamp in procesados:
            continue

        # Añadir esta línea para filtrar por "Aprobado" == "Sí"
        if fila.get("Aprobado", "").strip().lower() != "sí":
            continue

        # Obtener los valores del CSV
        nombre_lugar = fila.get("Nombre del lugar", "")
        descripcion = fila.get("Descripción", "")
        enlace = fila.get("Enlace", "")
        planta = fila.get("Planta", "")
        tipo = fila.get("Tipo", "").strip().strip('"').strip("'")
        latitud = float(fila.get("Coordenadas: latitud", 0))
        longitud = float(fila.get("Coordenadas: longitud", 0))

        # Redondear las coordenadas
        latitud_redondeada = redondear_coordenadas(latitud)
        longitud_redondeada = redondear_coordenadas(longitud)

        # Inferir campus
        campus = inferir_campus(latitud, longitud, gdf_campus)

        # Inferir edificio
        edificio = inferir_edificio(latitud, longitud, gdf_edificios, campus)

        # Si no se infirió edificio y no se infirió campus, buscar en todos los edificios
        if edificio is None and campus is None:
            edificio = inferir_edificio(latitud, longitud, gdf_edificios)

        # Si se infirió edificio pero no campus, inferir campus a partir del edificio
        if edificio is not None and campus is None:
            if edificio in campusBahiaAlgeciras:
                campus = "Bahía de Algeciras"
            elif edificio in campusCadiz:
                campus = "Cádiz"
            elif edificio in campusJerez:
                campus = "Jerez"
            elif edificio in campusPuertoReal:
                campus = "Puerto Real"

        # Obtener los códigos correspondientes
        codigo_campus = campus_codes.get(campus, "0")
        codigo_edificio = edificio_codes.get(edificio, "00")
        codigo_planta = planta_codes.get(planta, "00")
        codigo_tipo = tipo_codes_num.get(tipo, "00")

        # Solo crear el feature si campus y edificio son conocidos:
        # inferir_campus() e inferir_edificio() devuelven None cuando no
        # localizan el punto, y "Desconocido" es lo que queda grabado en los
        # features antiguos, así que hay que excluir ambos valores
        if campus not in (None, "Desconocido") and edificio not in (None, "Desconocido"):
            # ---------------- DEDUPLICACIÓN (fusión aditiva) ----------------
            # ¿Es este reporte de un punto que ya existe? Si lo es, NO se crea
            # feature ni idnum nuevo: la información NUEVA se AÑADE al gemelo
            # (nunca se suprime ni se sustituye nada de lo ya publicado).

            # 1) Marca de adecuacion.py ("Duplicado de"): el idnum del gemelo
            #    publicado o el Timestamp del gemelo del lote. La marca se
            #    verifica SIEMPRE contra el grupo: jamás puede fusionar puntos
            #    de campus/edificio distintos (o de planta distinta).
            marca = (fila.get("Duplicado de") or "").strip()
            objetivo = None
            if marca:
                if "/" in marca:
                    objetivo = features_por_timestamp.get(marca)  # gemelo del lote
                else:
                    objetivo = features_por_idnum.get(marca)      # gemelo publicado
                if objetivo is not None:
                    props_obj = objetivo["properties"]
                    planta_obj = dedup.normalizar_planta(props_obj.get("planta"))
                    planta_fila = dedup.normalizar_planta(planta)
                    if ((props_obj.get("campus"), props_obj.get("edificio")) != (campus, edificio)
                            or (planta_fila != "" and planta_obj != planta_fila)):
                        print(f"    Marca 'Duplicado de {marca}' ignorada para '{nombre_lugar}': el gemelo es de otro campus/edificio/planta")
                        objetivo = None  # grupo incompatible: la marca se ignora

            # 2) Sin marca (o no resuelta): detección barata R1/R2 con
            #    confirmación por coordenadas entre los features del grupo
            if objetivo is None:
                planta_fila = dedup.normalizar_planta(planta)
                if planta_fila == "":
                    # Sin planta declarada: candidatas de cualquier planta del edificio
                    candidatos_grupo = [f for (c, e, _), fs in features_por_grupo.items()
                                        if c == campus and e == edificio for f in fs]
                else:
                    candidatos_grupo = features_por_grupo.get((campus, edificio, planta_fila), [])
                candidatos = [
                    {"nombre": f["properties"].get("nombre") or "",
                     "lat": f["geometry"]["coordinates"][1],
                     "lon": f["geometry"]["coordinates"][0],
                     "feature": f}
                    for f in candidatos_grupo
                ]
                dup, descartados_grupo = dedup.detectar_duplicado(
                    nombre_lugar, latitud_redondeada, longitud_redondeada, candidatos)
                if dup is not None:
                    objetivo = dup["feature"]
                # Casan por nombre pero quedan lejos: sitios distintos -> aviso
                for d in descartados_grupo:
                    idnum_d = d["feature"]["properties"].get("idnum")
                    avisos_duplicados.append({
                        "timestamp": timestamp,
                        "idnum_existente": idnum_d,
                        "distancia_m": round(d["distancia_m"], 1)
                    })
                    print(f"    Aviso dedup: '{nombre_lugar}' casa por nombre con '{d['nombre']}' ({idnum_d}) pero dista {d['distancia_m']:.0f} m: no se fusiona")

            if objetivo is not None:
                # Fusión ADITIVA sobre el gemelo (índices incluidos: se muta
                # la feature in situ, así lo guardado siempre es lo vigente)
                props = objetivo["properties"]
                campos_actualizados = []
                conflictos = {}

                # descrip: se añade SOLO si aporta información nueva (si el
                # texto nuevo ya está contenido en el existente, no se añade)
                descrip_nueva = (descripcion or "").strip()
                descrip_actual = (props.get("descrip") or "").strip()
                if descrip_nueva and dedup.normalizar_nombre(descrip_nueva) not in dedup.normalizar_nombre(descrip_actual):
                    props["descrip"] = (descrip_actual + " " + descrip_nueva).strip()
                    campos_actualizados.append("descrip")

                # enlace: solo rellenando el vacío; con ambos llenos y
                # distintos, conflicto -> se mantiene el existente y queda
                # en el log para revisión manual
                enlace_nuevo = (enlace or "").strip()
                enlace_actual = (props.get("enlace") or "").strip()
                if enlace_nuevo and not enlace_actual:
                    props["enlace"] = enlace_nuevo
                    campos_actualizados.append("enlace")
                elif enlace_nuevo and enlace_actual and enlace_nuevo != enlace_actual:
                    conflictos["enlace"] = {"existente": enlace_actual, "nuevo": enlace_nuevo}
                    print(f"    Conflicto de enlace en {props.get('idnum')}: se mantiene '{enlace_actual}'; el nuevo queda en log.json")

                # tipo: solo rellenando vacío/desconocido (el idnum NUNCA cambia)
                tipo_nuevo_corto = tipo_codes_str.get((tipo or "").strip(), "")
                tipo_actual = (props.get("tipo") or "").strip()
                if tipo_actual in ("", "Desconocido") and tipo_nuevo_corto:
                    props["tipo"] = tipo_nuevo_corto
                    campos_actualizados.append("tipo")
                elif tipo_nuevo_corto and tipo_actual not in ("", "Desconocido") and tipo_nuevo_corto != tipo_actual:
                    # El tipo del gemelo se mantiene; queda solo constancia
                    conflictos["tipo"] = {"existente": tipo_actual, "nuevo": tipo_nuevo_corto}

                # coordenadas: solo se rellenan si el gemelo está en (0, 0)
                coords_obj = objetivo["geometry"]["coordinates"]
                if not dedup.coords_validas(coords_obj[1], coords_obj[0]) and dedup.coords_validas(latitud_redondeada, longitud_redondeada):
                    objetivo["geometry"]["coordinates"] = [longitud_redondeada, latitud_redondeada]
                    campos_actualizados.append("coordenadas")

                # Auditoría de la fusión en log.json
                fusion = {
                    "timestamp": timestamp,
                    "idnum": props.get("idnum"),
                    "campos_actualizados": campos_actualizados,
                }
                if nombre_lugar and nombre_lugar != props.get("nombre"):
                    fusion["alias"] = nombre_lugar
                if conflictos:
                    fusion["conflictos"] = conflictos
                fusiones.append(fusion)
                print(f"    Fusión aditiva: '{nombre_lugar}' se incorpora a '{props.get('nombre')}' ({props.get('idnum')}); campos: {campos_actualizados or 'sin cambios'}")

                # El aporte queda procesado: fusionado en el gemelo, no
                # genera feature ni consume número de idnum
                procesados.add(timestamp)
                continue

            # ---------------- Creación del feature (no es duplicado) ----------------
            # Incrementar el contador de ID solo para los features creadados
            # (así las filas excluidas y las fusionadas no consumen idnum)
            id_counter[campus][edificio][planta][tipo] += 1
            id_num = id_counter[campus][edificio][planta][tipo]

            # Formatear el ID
            id_formateado = f"{codigo_campus}{codigo_edificio}{codigo_planta}{codigo_tipo}{id_num:02d}"

            planta_value = planta
            if planta in ["Baja", "Sótano"]:
                planta_value = planta.lower()
            else:
                planta_value = planta.split()[-1]

            feature = {
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

            features_nuevos.append(feature)

            # Registrar el feature en los índices de deduplicación (para las
            # filas duplicadas que vengan después en este mismo lote)
            features_por_grupo.setdefault((campus, edificio, dedup.normalizar_planta(planta)), []).append(feature)
            features_por_idnum[id_formateado] = feature
            features_por_timestamp[timestamp] = feature

            # FIX 24-10: el aporte queda procesado SOLO cuando su feature se
            # ha creado (está publicado). Todo lo demás se reexamina en cada
            # ejecución sin coste (sin LLM) hasta que le toque publicarse.
            procesados.add(timestamp)

    # Combinar features antiguos y nuevos
    features_combinados = features_antiguos + features_nuevos

    # Antes de ordenar, asignar valores por defecto a los campos que puedan ser None
    for feature in features_combinados:
        props = feature["properties"]
        if props["campus"] is None:
            props["campus"] = "Desconocido"
        if props["edificio"] is None:
            props["edificio"] = "Desconocido"
        if props["planta"] is None:
            props["planta"] = "Desconocido"
        if props["tipo"] is None:
            props["tipo"] = "Desconocido"

    # Ordenar los features combinados
    features_ordenados = sorted(
        features_combinados,
        key=lambda x: (
            x["properties"]["campus"],
            x["properties"]["edificio"],
            x["properties"]["planta"],
            x["properties"]["tipo"]
        )
    )

    # Guardar el GeoJSON completo
    feature_collection = {
        "type": "FeatureCollection",
        "features": features_ordenados
    }
    with open(ruta_geojson, 'w', encoding='utf-8') as f:
        json.dump(feature_collection, f, indent=4, ensure_ascii=False)

    # Guardar el log actualizado (procesados + contadores + auditoría dedup)
    guardar_log(ruta_log, procesados, id_counter, fusiones, avisos_duplicados)

    return feature_collection

# %%
# Rutas del CSV
ruta_csv = 'map_data.csv'

# Generar el JSON
feature_collection = leer_csv_y_generar_json(ruta_csv)

# Guardar el JSON en un archivo
ruta_json = 'map_data.geojson'
with open(ruta_json, 'w', encoding='utf-8') as archivo_json:
    json.dump(feature_collection, archivo_json, ensure_ascii=False, indent=2)
