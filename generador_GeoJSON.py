# Importar las bibliotecas necesarias
import csv
import json
from collections import defaultdict

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
    "Aula": "aula",
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

def redondear_coordenadas(coord):
    """Redondea una coordenada a 6 decimales si tiene más."""
    try:
        coord_float = float(coord)
        return round(coord_float, 6)
    except ValueError:
        return coord

def leer_csv_y_generar_json(ruta_csv):
    """Lee el CSV y genera el JSON con la estructura solicitada."""
    features = []

    # Diccionario para llevar el conteo de IDs por campus, edificio, planta y tipo
    id_counter = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))

    with open(ruta_csv, mode='r', encoding='utf-8') as archivo_csv:
        lector_csv = csv.DictReader(archivo_csv)

        for fila in lector_csv:
            # Obtener los valores del CSV
            nombre_lugar = fila.get("Nombre del lugar", "")
            descripcion = fila.get("Descripción", "")
            campus = fila.get("Campus", "")
            edificio = fila.get("Edificio o Centro", "")
            planta = fila.get("Planta", "")
            tipo = fila.get("Tipo", "")
            latitud = fila.get("Coordenadas: latitud", "")
            longitud = fila.get("Coordenadas: longitud", "")

            # Redondear las coordenadas
            latitud_redondeada = redondear_coordenadas(latitud)
            longitud_redondeada = redondear_coordenadas(longitud)

            # Obtener los códigos correspondientes
            codigo_campus = campus_codes.get(campus, "0")
            codigo_edificio = edificio_codes.get(edificio, "00")
            codigo_planta = planta_codes.get(planta, "00")
            codigo_tipo = tipo_codes_num.get(tipo, "00")

            # Incrementar el contador de ID para este grupo
            id_counter[campus][edificio][planta][tipo] += 1
            id_num = id_counter[campus][edificio][planta][tipo]

            # Formatear el ID
            id_formateado = f"{codigo_campus}{codigo_edificio}{codigo_planta}{codigo_tipo}{id_num:02d}"

            # Crear el feature
            planta_value = planta
            if planta in ["Baja", "Sótano"]:
                planta_value = planta.lower()  # "baja" o "sótano"
            else:
                planta_value = planta.split()[-1]  # Toma solo el número de la planta

            feature = {
                "type": "Feature",
                "properties": {
                    "clase": "espacio",
                    "nombre": nombre_lugar,
                    "descrip": descripcion,
                    "tipo": tipo_codes_str.get(tipo, ""),
                    "planta": planta_value,
                    "edificio": edificio,
                    "campus": campus,
                    "idnum": id_formateado,
                    "favourite": False,
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [longitud_redondeada, latitud_redondeada]
                }
            }

            features.append(feature)

    # Ordenar los features según la jerarquía: campus > edificio > planta > tipo
    features_ordenados = sorted(
        features,
        key=lambda x: (
            x["properties"]["campus"],
            x["properties"]["edificio"],
            x["properties"]["planta"],
            x["properties"]["tipo"]
        )
    )

    # Crear el FeatureCollection
    feature_collection = {
        "type": "FeatureCollection",
        "features": features_ordenados
    }

    return feature_collection

# Ruta del archivo CSV
ruta_csv = 'map_data.csv'

# Generar el JSON
feature_collection = leer_csv_y_generar_json(ruta_csv)

# Guardar el JSON en un archivo
ruta_json = 'map_data.geojson'
with open(ruta_json, 'w', encoding='utf-8') as archivo_json:
    json.dump(feature_collection, archivo_json, ensure_ascii=False, indent=2)
