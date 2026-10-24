# %%
# dedup.py — Detección de reportes duplicados de un mismo lugar (GadirE).
#
# Módulo compartido entre adecuacion.py y generador_map_data.py: reúne en un
# solo sitio las reglas de detección para que ambos programas decidan igual.
#
# Reglas de detección (los candidatos deben venir ya filtrados por planta —y,
# en el generador, por campus y edificio—):
#   R1: nombre exacto tras normalizar (unidecode + minúsculas + sin puntuación).
#   R2: nombre "parecido": ambos nombres con longitud >= LONG_MINIMA_FUZZY y,
#       además, similitud Levenshtein >= RATIO_SIMILITUD o un nombre es
#       subconjunto de tokens del otro (ignorando conectores como "de", "del",
#       "la"...). Los nombres cortos (FC2, FC4, FC5...) SOLO pueden casar por
#       R1: jamás se fusionan por parecido ("FC2" y "FC4" son aulas distintas).
#   Confirmación por coordenadas: si ambos puntos son válidos, la fusión solo
#       procede si distan <= UMBRAL_METROS; si distan más, el candidato se
#       descarta y se devuelve como aviso (casan por nombre pero son sitios
#       distintos). Coordenadas ausentes (0, 0) cuentan como compatibles.
#   R3 (solo adecuacion.py, con LLM): mismo sitio por planta y coordenadas
#       pero nombre que no casa por R1/R2 -> una llamada corta al modelo decide
#       si son el mismo lugar (matching semántico, p. ej. renombres).

import json
import math
import unidecode
import Levenshtein

# %%
# Constantes de la deduplicación (ajustadas con los datos reales del CSV:
# los dos "Cuarto de baño" de FC distan 57,7 m y deben quedar separados; las
# dos "Fuente de agua" distan 101,4 m y también; las dos salas de estudio de
# la FC distan 5 m y son el mismo sitio)
UMBRAL_METROS = 50        # Distancia máxima (m) para confirmar duplicado por coordenadas
LONG_MINIMA_FUZZY = 8      # Longitud mínima del nombre normalizado para aplicar R2
RATIO_SIMILITUD = 0.8      # Similitud Levenshtein mínima para R2

# Conectores que se ignoran al comparar tokens de nombres
CONECTORES = {"de", "del", "la", "el", "los", "las", "un", "una", "y", "o", "en", "para", "of", "the"}

# Tipo largo del CSV a partir del tipo corto de las propiedades del GeoJSON
# (para copiar el tipo del gemelo publicado a la fila duplicada)
TIPO_LARGO_POR_CORTO = {
    "descanso": "Área de descanso",
    "aseo": "Aseo o vestuario",
    "aula": "Aula",
    "biblio": "Biblioteca o sala de estudio",
    "cafete": "Cafetería, fuente o máquina",
    "despacho": "Despacho",
    "lab": "Laboratorio o taller",
    "repre": "Representación de estudiantes",
    "emergencia": "Salida de emergencia o punto de encuentro",
    "salon": "Salón de Actos o de Grado",
    "transporte": "Transporte",
    "unidad": "Unidades o servicios",
}

# %%
def normalizar_nombre(nombre):
    """
    Normaliza un nombre de lugar para comparar: minúsculas, sin tildes ni
    caracteres especiales y sin signos de puntuación.

    Parameters
    ----------
    nombre : str
        Nombre del lugar tal cual viene del formulario o del GeoJSON.

    Returns
    -------
    str
        Nombre normalizado (vacío si el nombre era nulo o vacío).
    """
    if not nombre:
        return ""
    texto = str(nombre).lower()
    texto = unidecode.unidecode(texto)          # quita tildes y caracteres especiales
    texto = "".join(c for c in texto if c.isalnum() or c.isspace())  # quita puntuación
    return " ".join(texto.split())               # colapsa espacios sobrantes

# %%
def tokens_sin_conectores(nombre):
    """
    Devuelve el conjunto de tokens significativos del nombre, sin conectores
    ("Cafetería del CASEM" -> {"cafeteria", "casem"}).

    Parameters
    ----------
    nombre : str
        Nombre del lugar.

    Returns
    -------
    set of str
        Tokens en minúscula, sin tildes y sin conectores.
    """
    norm = normalizar_nombre(nombre)
    if not norm:
        return set()
    # Un nombre es subconjunto semántico de otro si todos sus tokens están
    # en el otro, ignorando conectores ("de", "del", "la"...)
    return {t for t in norm.split() if t not in CONECTORES}

# %%
def normalizar_planta(planta):
    """
    Normaliza una planta para poder comparar filas del CSV y features del
    GeoJSON entre sí ("Planta 1" -> "1", "Baja" -> "baja", "Sótano" -> "sotano").

    Parameters
    ----------
    planta : str
        Valor de la planta: columna "Planta" del CSV o propiedad "planta"
        de una feature ("baja", "sotano", "1", ...).

    Returns
    -------
    str
        Planta normalizada ("" si era nula, vacía o "nan").
    """
    if not planta or str(planta).lower() == "nan":
        return ""
    p = str(planta).strip().lower()
    p = unidecode.unidecode(p)                   # "sótano" -> "sotano"
    if p.startswith("planta"):
        p = p[len("planta"):].strip()            # "planta 1" -> "1"
    return p

# %%
def coords_validas(lat, lon):
    """
    Indica si un punto (lat, lon) son coordenadas reales (el (0, 0) cuenta
    como ausente: nadie reporta un lugar en el Golfo de Guinea).

    Parameters
    ----------
    lat : float
        Latitud.
    lon : float
        Longitud.

    Returns
    -------
    bool
        True si el punto es válido para medir distancias.
    """
    try:
        la, lo = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    return not (la == 0 and lo == 0)

# %%
def distancia_haversine(lat1, lon1, lat2, lon2):
    """
    Distancia en metros entre dos puntos (lat, lon) con la fórmula de
    haversine (esfera de radio terrestre medio).

    Parameters
    ----------
    lat1, lon1 : float
        Coordenadas del primer punto.
    lat2, lon2 : float
        Coordenadas del segundo punto.

    Returns
    -------
    float
        Distancia en metros entre los dos puntos.
    """
    R = 6371000.0                                # radio terrestre medio (m)
    rad = math.radians
    dlat = rad(float(lat2) - float(lat1))
    dlon = rad(float(lon2) - float(lon1))
    # haversine: seno de medio delta, al cuadrado, en lat y en lon (corregido por coseno de latitud)
    h = math.sin(dlat / 2) ** 2 + math.cos(rad(float(lat1))) * math.cos(rad(float(lat2))) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))

# %%
def _digitos(nombre):
    """
    Conjunto de dígitos que aparecen en un nombre normalizado: los números de
    un nombre son identificadores del lugar (aula FC2, despacho 305...).

    Parameters
    ----------
    nombre : str
        Nombre del lugar.

    Returns
    -------
    set of str
        Dígitos únicos del nombre.
    """
    return {c for c in normalizar_nombre(nombre) if c.isdigit()}

# %%
def _casa_por_nombre(nombre_a, nombre_b):
    """
    Compara dos nombres con las reglas R1 (exacto normalizado) y R2
    (parecido con longitud mínima: similitud o subconjunto de tokens).

    Parameters
    ----------
    nombre_a, nombre_b : str
        Nombres a comparar.

    Returns
    -------
    tuple of (bool, float)
        (casa, ratio): si casan por nombre y con qué similitud (1.0 para R1).
    """
    na, nb = normalizar_nombre(nombre_a), normalizar_nombre(nombre_b)
    if not na or not nb:
        return False, 0.0
    # R1: exacto tras normalizar
    if na == nb:
        return True, 1.0
    # R2: solo nombres largos (FC2/FC4 y similares jamás casan por parecido)
    if len(na) < LONG_MINIMA_FUZZY or len(nb) < LONG_MINIMA_FUZZY:
        return False, 0.0
    # FIX v14: si los NÚMEROS de los nombres difieren, son lugares distintos:
    # "Aula FC2" y "Aula FC4" miden 8 caracteres (pasaban el filtro de longitud)
    # y casaban por similitud con coordenadas cercanas, fundiéndose. Los dígitos
    # de un nombre son su identificador: con números distintos no hay R2.
    if _digitos(na) != _digitos(nb):
        return False, 0.0
    ratio = Levenshtein.ratio(na, nb)
    if ratio >= RATIO_SIMILITUD:
        return True, ratio
    # Subconjunto de tokens: "cafeteria casem" dentro de "cafeteria del casem"
    ta, tb = tokens_sin_conectores(na), tokens_sin_conectores(nb)
    if ta and tb and (ta <= tb or tb <= ta):
        return True, max(ratio, 0.8)
    return False, ratio

# %%
def filtrar_por_planta(planta, candidatos):
    """
    Filtra los candidatos a duplicado por planta: planta distinta = lugar
    distinto. Una planta vacía en el reporte casa con cualquier cosa (sin
    planta no hay evidencia de ser distinta planta).

    Parameters
    ----------
    planta : str
        Planta del reporte nuevo (columna "Planta" del CSV).
    candidatos : list of dict
        Candidatos (cada uno con clave 'planta').

    Returns
    -------
    list of dict
        Candidatos con la misma planta (todos si la del reporte es vacía).
    """
    p = normalizar_planta(planta)
    if p == "":
        return list(candidatos)
    return [c for c in candidatos if normalizar_planta(c.get("planta", "")) == p]

# %%
def detectar_duplicado(nombre, lat, lon, candidatos):
    """
    Busca entre los candidatos uno que sea el mismo lugar reportado de nuevo.

    Parameters
    ----------
    nombre : str
        Nombre del lugar del reporte nuevo.
    lat, lon : float
        Coordenadas del reporte nuevo ((0, 0) si vienen vacías o inválidas).
    candidatos : list of dict
        Cada dict debe llevar 'nombre', 'lat' y 'lon'; el resto de claves
        (tipo, idnum, feature...) se devuelven tal cual para que el llamador
        sepa con qué ha casado.

    Returns
    -------
    tuple of (dict or None, list of dict)
        (duplicado, descartados): el candidato duplicado (None si no hay) y
        la lista de candidatos que casaron por nombre pero se descartaron por
        quedar a más de UMBRAL_METROS (cada uno con 'distancia_m' añadida).
    """
    if not normalizar_nombre(nombre):
        return None, []
    mejor = None          # (clave de orden, candidato): R1 antes que R2, más similitud, más cerca
    descartados = []
    for cand in candidatos:
        casa, ratio = _casa_por_nombre(nombre, cand.get("nombre"))
        if not casa:
            continue
        # Confirmación por coordenadas: cerca (o sin coordenadas) -> duplicado;
        # lejos -> casan por nombre pero son sitios distintos (aviso)
        if coords_validas(lat, lon) and coords_validas(cand.get("lat"), cand.get("lon")):
            d = distancia_haversine(lat, lon, cand["lat"], cand["lon"])
            if d > UMBRAL_METROS:
                desc = dict(cand)
                desc["distancia_m"] = d
                descartados.append(desc)
                continue
            distancia = d
        else:
            distancia = float("inf")            # sin coordenadas: compatible con todo
        # Orden de preferencia: R1 antes que R2; a igualdad, mayor similitud y menor distancia
        clave = (0 if ratio == 1.0 else 1, -ratio, distancia)
        if mejor is None or clave < mejor[0]:
            mejor = (clave, cand)
    return (mejor[1] if mejor else None), descartados

# %%
def candidatos_para_llm(nombre, planta, lat, lon, candidatos):
    """
    Candidatos ambiguos para la vía semántica R3: misma planta, coordenadas
    válidas a menos de UMBRAL_METROS y nombre que NO casa por R1/R2 (esos ya
    los resuelve la vía barata). Ordenados por distancia.

    Parameters
    ----------
    nombre : str
        Nombre del lugar del reporte nuevo.
    planta : str
        Planta del reporte nuevo.
    lat, lon : float
        Coordenadas del reporte nuevo.
    candidatos : list of dict
        Candidatos ya filtrados por planta ('nombre', 'lat', 'lon').

    Returns
    -------
    list of dict
        Candidatos a preguntar al LLM, de más cerca a más lejos.
    """
    if not coords_validas(lat, lon):
        return []
    resultado = []
    for cand in filtrar_por_planta(planta, candidatos):
        if not coords_validas(cand.get("lat"), cand.get("lon")):
            continue
        casa, _ = _casa_por_nombre(nombre, cand.get("nombre"))
        if casa:
            continue                            # ya resuelto por la vía barata
        d = distancia_haversine(lat, lon, cand["lat"], cand["lon"])
        if d <= UMBRAL_METROS:
            resultado.append((d, cand))
    # De más cerca a más lejos: lo más verosímil primero
    resultado.sort(key=lambda par: par[0])
    return [cand for _, cand in resultado]

# %%
def mismo_lugar_llm(nombre_a, nombre_b, modelo="mistral:7b"):
    """
    Vía semántica R3: pregunta al LLM si dos nombres designan el mismo lugar
    concreto de la universidad. Solo para casos ambiguos (una llamada corta).

    Parameters
    ----------
    nombre_a, nombre_b : str
        Nombres a comparar.
    modelo : str, optional
        Modelo de Ollama a usar (mistral:7b por defecto).

    Returns
    -------
    bool
        True si el modelo responde que son el mismo lugar (False ante
        cualquier duda o fallo: no fusionar es lo seguro).
    """
    import ollama                              # import perezoso: solo lo usa adecuacion.py
    prompt = (
        f'¿"{nombre_a}" y "{nombre_b}" son el mismo lugar concreto de la Universidad de Cádiz '
        f'(la misma instalación, aula, despacho, servicio o punto físicamente)?\n'
        'Responde únicamente "Sí" o "No".'
    )
    try:
        respuesta = ollama.generate(model=modelo, prompt=prompt)["response"].strip().lower()
    except Exception:
        return False                            # ante cualquier fallo: no fusionar
    # Acepta "sí"/"si" con o sin punto final; cualquier otra cosa es "no"
    return respuesta.strip(".!").split()[0:1] in (["sí"], ["si"])

# %%
def cargar_features_publicados(ruta_geojson):
    """
    Lee las features ya publicadas de map_data.geojson para usarlas como
    candidatas a duplicado (con su idnum, para la marca "Duplicado de").

    Parameters
    ----------
    ruta_geojson : str
        Ruta al GeoJSON publicado (en la misma carpeta de trabajo).

    Returns
    -------
    list of dict
        Una entrada por feature: nombre, planta, lat, lon, tipo (corto) e
        idnum. Lista vacía si el archivo no existe (regeneración completa)
        o está corrupto.
    """
    try:
        with open(ruta_geojson, 'r', encoding='utf-8') as f:
            geojson = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    publicados = []
    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [0, 0])
        publicados.append({
            "nombre": props.get("nombre") or "",
            "planta": props.get("planta") or "",
            "lat": coords[1] if isinstance(coords, list) and len(coords) > 1 else 0.0,
            "lon": coords[0] if isinstance(coords, list) else 0.0,
            "tipo": props.get("tipo") or "",   # tipo CORTO de las propiedades
            "idnum": props.get("idnum") or "",
        })
    return publicados
