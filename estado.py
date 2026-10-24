# estado.py — Radiografía del estado del proyecto, sin ejecutar nada.
#
# Lee (y sólo lee) log.json, map_data.csv y map_data.geojson y muestra:
#   - Los archivos y su antigüedad/tamaño.
#   - Las últimas ejecuciones registradas (modo, duración, resultados).
#   - Conteos: procesados, features, fusiones, avisos, conflictos pendientes.
#   - Filas del CSV por veredicto (Sí/No/Revisar) y marcas de duplicado.
#   - Comprobaciones: idnum únicos, features sin campus, filas aprobadas
#     todavía sin publicar (pendientes de ubicación o por fusionar).
#
# No usa LLM ni KML: es instantáneo y seguro ejecutarlo cuando sea.

import csv
import json
import sys
import time

import registro


def _leer_json(ruta):
    """
    Lee un JSON tolerando ausencia o corrupción.

    Parameters
    ----------
    ruta : Path
        Archivo a leer.

    Returns
    -------
    dict or None
        El contenido, o None si no existe o está corrupto.
    """
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def main():
    """
    Imprime el estado completo del proyecto y devuelve 0 siempre.

    Returns
    -------
    int
        0 (es una lectura informativa: nunca falla la operación).
    """
    base = registro.RUTA_PROYECTO

    # ---------------- Archivos ----------------
    print("=== Estado de GadirE (sólo lectura) ===")
    for nombre in ("log.json", "map_data.csv", "map_data_form.csv", "map_data.geojson"):
        ruta = base / nombre
        if ruta.exists():
            edad_h = (time.time() - ruta.stat().st_mtime) / 3600
            print(f"  {nombre:24} {ruta.stat().st_size:8d} bytes  (modificado hace {edad_h:.1f} h)")
        else:
            print(f"  {nombre:24} NO EXISTE")

    # ---------------- log.json ----------------
    log = _leer_json(base / "log.json")
    if log is None:
        print("  log.json: ausente o corrupto (el siguiente arranque regenera de cero)")
    else:
        procesados = log.get("procesados", [])
        fusiones = log.get("fusiones", [])
        avisos = log.get("avisos_duplicados", [])
        # Conflictos pendientes: fusiones que dejaron un enlace o tipo distinto
        conflictos = [f for f in fusiones if f.get("conflictos")]
        ejecuciones = log.get("ejecuciones", [])
        print(f"  procesados: {len(procesados)}   fusiones: {len(fusiones)}   "
              f"avisos: {len(avisos)}   conflictos pendientes: {len(conflictos)}")
        for c in conflictos[-5:]:
            print(f"    conflicto: {c.get('timestamp')} en {c.get('idnum')}: {c.get('conflictos')}")
        if ejecuciones:
            print(f"  últimas ejecuciones ({len(ejecuciones)} registradas):")
            for e in ejecuciones[-5:]:
                print(f"    {e.get('fecha')} modo={e.get('modo')} {e.get('duracion_s', '?')}s "
                      f"publicadas={e.get('publicadas', '?')} fusionadas={e.get('fusionadas', '?')} "
                      f"features={e.get('features_finales', '?')}")
        else:
            print("  sin ejecuciones registradas (log anterior a v14)")

    # ---------------- map_data.csv ----------------
    filas_csv, veredictos, duplicados = [], {}, 0
    try:
        with open(base / "map_data.csv", "r", encoding="utf-8") as f:
            filas_csv = list(csv.DictReader(f))
        for fila in filas_csv:
            veredicto = (fila.get("Aprobado") or "").strip() or "(sin veredicto)"
            veredictos[veredicto] = veredictos.get(veredicto, 0) + 1
            if (fila.get("Duplicado de") or "").strip():
                duplicados += 1
        print(f"  map_data.csv: {len(filas_csv)} filas; por veredicto: {veredictos}; "
              f"marcadas 'Duplicado de': {duplicados}")
    except FileNotFoundError:
        print("  map_data.csv: NO EXISTE (ejecuta update.py antes de mirar el estado)")

    # ---------------- map_data.geojson ----------------
    geojson = _leer_json(base / "map_data.geojson")
    if geojson is None:
        print("  map_data.geojson: ausente o corrupto")
    else:
        features = geojson.get("features", [])
        idnums = [f.get("properties", {}).get("idnum") for f in features]
        repetidos = {i for i in idnums if idnums.count(i) > 1}
        sin_campus = [f for f in features if not f.get("properties", {}).get("campus") or
                      f["properties"]["campus"] == "Desconocido"]
        print(f"  geojson: {len(features)} features; idnum únicos: {len(set(idnums))}"
              f"{' ¡REPETIDOS: ' + str(sorted(repetidos)) + '!' if repetidos else ''}; "
              f"sin campus: {len(sin_campus)}")

        # Aprobadas aún sin publicar: candidatas a quedar fuera por ubicación
        if log is not None and filas_csv:
            procesados = set(log.get("procesados", []))
            pendientes = [f for f in filas_csv
                          if (f.get("Aprobado") or "").strip().lower() == "sí"
                          and (f.get("Timestamp") or "") not in procesados]
            print(f"  aprobadas sin publicar (reexaminadas en cada update): {len(pendientes)}")
            for fila in pendientes[:10]:
                print(f"    {fila.get('Timestamp')}  {fila.get('Nombre del lugar')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
