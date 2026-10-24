#!/usr/bin/env python3
# review.py — Manual review of pending entries and published points (GadirE).
#
# Two jobs in one tool:
#
#   1) PENDING entries: rows of map_data.csv whose verdict is
#      "Revisar manualmente" (the moderation LLM could not decide). The tool
#      shows them, asks, and saves the decision in the CSV:
#        - "yes" -> Aprobado="Sí" and "Revisado" is CLEARED, so the next
#          update reuses the stored verdict (no revision LLM call) but does
#          re-evaluate duplicates (additive fusion) and assigns the type.
#        - "no"  -> Aprobado="No" (the generator re-checks it cheaply on
#          every run, in case the verdict is ever changed by hand).
#
#   2) PUBLISHED points (by idnum): inspect, edit any field, or retract
#      (remove from the map). The working map_data.geojson is the source of
#      truth for published points, so edits and retractions are applied
#      there; the source row in map_data.csv is updated too, so a reset does
#      not resurrect a retracted point or lose a manual correction.
#
# Usage:
#     python3 review.py                         oldest pending: show + ask
#     python3 review.py list                    every pending entry with its id
#     python3 review.py all                    review all pending, one by one
#     python3 review.py "<timestamp>"           show that entry and ask
#     python3 review.py "<timestamp>" yes|no    answer directly, without showing
#     python3 review.py point <idnum>           show a published point
#     python3 review.py point <idnum> retract [yes]   remove it (asks unless
#                                                "yes" is given as 3rd arg)
#     python3 review.py point <idnum> set <field> <value...>
#         fields: name, description, link, type, floor (alias plant),
#                 latitude, longitude
#
# The identifier of a pending entry is its form Timestamp (unique per
# submission; quote it, it contains spaces). The identifier of a published
# point is its idnum.
#
# NOTE: answers are typed in English ("yes"/"no"), but the CSV keeps the
# exact Spanish values the pipeline expects: "Sí" / "No". Never edit
# map_data_form.csv by hand: the next update re-downloads it.

import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

# Verdict that marks a row as pending manual review (exact CSV value)
PENDING_VERDICT = "Revisar manualmente"

# Accepted answers on the command line / prompt (British English UI)
_ANSWERS_YES = {"yes", "y"}
_ANSWERS_NO = {"no", "n"}

# CSV columns this tool may write. All are forced to text before writing:
# pandas loads a fully-empty column as float64 and .at would abort (the v16
# dtype crash, kept as a guard here for the very same reason)
_COLUMNS_WRITTEN = ("Aprobado", "Revisado", "Nombre del lugar", "Descripción",
                    "Enlace", "Tipo", "Planta",
                    "Coordenadas: latitud", "Coordenadas: longitud")

# Command fields accepted by `point <idnum> set`, mapped to (GeoJSON property,
# CSV column of the source row). None means the geometry is edited instead
_SET_FIELDS = {
    "name": ("nombre", "Nombre del lugar"),
    "description": ("descrip", "Descripción"),
    "link": ("enlace", "Enlace"),
    "type": ("tipo", "Tipo"),
    "floor": ("planta", "Planta"),
    "plant": ("planta", "Planta"),                    # alias for readability
    "latitude": (None, "Coordenadas: latitud"),
    "longitude": (None, "Coordenadas: longitud"),
}

# Fields that are never editable: the idnum is the public identifier of the
# point and is baked into log.json, log counters and the frontend
_FORBIDDEN_FIELDS = ("idnum", "campus", "edificio", "clase")

# Long type name for every short type code (mirror of dedup.TIPO_LARGO_POR_CORTO;
# used only when dedup.py cannot be imported from the project folder)
_TIPO_LARGO_POR_CORTO = {
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

# Tolerance (degrees) to match a feature's coordinates against CSV rows:
# features store coordinates rounded to 6 decimals, the CSV may keep more
_TOL_COORDS = 1e-5


# %% ------------------------- project and type maps -------------------------

def _project_dir():
    """
    Locate the project folder (the one holding the state files).

    Checks the GADIRE_RUTA_PROYECTO environment variable first (same
    convention as pipeline.py), then the usual layouts: gen_geojson/ under
    the working directory, the working directory itself (flat layout), and
    the same two relative to this script's folder.

    Returns
    -------
    Path
        Folder where map_data.csv / map_data.geojson live.
    """
    env = os.environ.get("GADIRE_RUTA_PROYECTO")
    if env:
        return Path(env)
    cwd = Path.cwd()
    base = Path(__file__).resolve().parent
    # gen_geojson/ layouts first, then the flat layout, both from the cwd and
    # from the folder of this script (covers running from the repo root and
    # from inside either folder)
    for candidate in (cwd / "gen_geojson", cwd, base / "gen_geojson", base):
        if (candidate / "map_data.csv").exists():
            return candidate
    return cwd / "gen_geojson" if (cwd / "gen_geojson").exists() else cwd


def _tipo_maps(project):
    """
    Type maps long name <-> short code, reusing dedup.py when possible.

    Parameters
    ----------
    project : Path
        Project folder (dedup.py lives there).

    Returns
    -------
    tuple of (dict, dict)
        (short code by long name, long name by short code).
    """
    try:
        # dedup.py is a sibling of the state files: add the folder to the
        # import path just for this lookup
        sys.path.insert(0, str(project))
        import dedup
        largo_por_corto = dict(dedup.TIPO_LARGO_POR_CORTO)
    except Exception:
        # Fallback: the mirrored copy above (kept in sync with dedup.py)
        largo_por_corto = dict(_TIPO_LARGO_POR_CORTO)
    corto_por_largo = {v: k for k, v in largo_por_corto.items()}
    return corto_por_largo, largo_por_corto


def _force_text_columns(df, columns):
    """
    Force the given CSV columns to text before writing with .at.

    A column that was empty in every row is loaded as float64 and writing a
    string into it aborts (the v16 crash): cast to object first, exactly as
    moderation.py does.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame of the accumulated CSV (modified in place).
    columns : iterable of str
        Column names this tool is about to write.
    """
    for col in columns:
        if col in df.columns and df[col].dtype != object:
            df[col] = df[col].astype(object)


# %% ------------------------------ JSON helpers ------------------------------

def _load_json(ruta):
    """
    Load a JSON file tolerating absence or corruption.

    Returns
    -------
    dict or None
        The parsed content, or None if missing or corrupt.
    """
    try:
        with open(ruta, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _save_json(ruta, datos, indent=2):
    """
    Save a JSON file atomically (tmp file + os.replace), same format as the
    generator: no ASCII escaping.

    Parameters
    ----------
    ruta : Path
        Destination file.
    datos : dict
        Content to write.
    indent : int, optional
        Indentation (2 for the GeoJSON, 4 for log.json, as the pipeline does).
    """
    tmp = ruta.parent / (ruta.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=indent)
    os.replace(tmp, ruta)                 # atomic: old or new, never a hybrid


def _backup(project, nombres):
    """
    Copy the state files into backups/review_<timestamp>/ before mutating.

    Parameters
    ----------
    project : Path
        Project folder (backups/ lives inside it).
    nombres : iterable of str
        File names to back up (skipped silently if missing).

    Returns
    -------
    Path or None
        The backup folder, or None if there was nothing to back up.
    """
    carpeta = project / "backups" / ("review_" + time.strftime("%Y%m%d_%H%M%S"))
    guardados = []
    for nombre in nombres:
        origen = project / nombre
        if origen.exists():
            guardados.append(origen)
    if not guardados:
        return None
    carpeta.mkdir(parents=True, exist_ok=True)
    for origen in guardados:
        shutil.copy2(origen, carpeta / origen.name)
    return carpeta


# %% --------------------------- pending entries ---------------------------

def _cell(df, idx, columna):
    """
    Cell value ready to print (empty cells show as "(empty)").
    """
    v = df.at[idx, columna]
    if v is None or (isinstance(v, float) and v != v) or str(v).strip() == "":
        return "(empty)"
    return str(v).strip()


def _pending_indices(df):
    """
    Indices of the pending rows ("Revisar manualmente"), oldest first by
    Timestamp. Rows with an unreadable Timestamp go last.
    """
    pendientes = []
    for idx, fila in df.iterrows():
        # NaN (empty cell) never equals the verdict: filtered out on its own
        if fila.get("Aprobado") == PENDING_VERDICT:
            pendientes.append(idx)

    def key(idx):
        try:
            # Form Timestamps are DD/MM/YYYY HH:MM:SS
            return datetime.strptime(_cell(df, idx, "Timestamp"), "%d/%m/%Y %H:%M:%S")
        except ValueError:
            return datetime.max               # unreadable: end of the queue

    return sorted(pendientes, key=key)


def _print_entry(df, idx, posicion=None, total=None):
    """
    Print a pending entry with all its data, aligned.
    """
    if posicion is not None:
        print(f"── Entry {posicion} of {total} " + "─" * 30)
    else:
        print("─" * 58)
    etiquetas = list(df.columns)
    ancho = max(len(str(e)) for e in etiquetas)
    for etiqueta in etiquetas:
        print(f"  {str(etiqueta):<{ancho}}  {_cell(df, idx, etiqueta)}")
    print("─" * 58)


def _normalise_answer(texto):
    """
    Translate what the user typed into "Sí", "No" or None (no decision).

    The UI is British English ("yes"/"no"); the CSV values stay Spanish.
    """
    limpio = (texto or "").strip().lower()
    if limpio in _ANSWERS_YES:
        return "Sí"
    if limpio in _ANSWERS_NO:
        return "No"
    return None


def _ask():
    """
    Ask over the keyboard whether to include the entry (EOF or Enter leave
    it pending; nothing is written without a decision).
    """
    try:
        texto = input("Include this entry in the map? (yes/no, Enter to leave it pending): ")
    except EOFError:
        return None                          # stdin closed: no decision
    return _normalise_answer(texto)


def _apply_decision(df, idx, decision):
    """
    Apply a decision to one row of the CSV (with the v16 dtype guard).

    Returns
    -------
    tuple of (str, str)
        (verdict written, what will happen in the next update).
    """
    _force_text_columns(df, ("Aprobado", "Revisado"))
    if decision == "Sí":
        df.at[idx, "Aprobado"] = "Sí"
        # Clear "Revisado": the next update reuses the stored verdict (no
        # revision LLM call) but does evaluate duplicates and the type
        df.at[idx, "Revisado"] = ""
        return "Sí", "it will be re-examined (duplicates + type) in the next update"
    df.at[idx, "Aprobado"] = "No"
    return "No", "it will not be published (re-checked cheaply on every update)"


def _identify(df, identificador):
    """
    Find the row whose Timestamp matches the given identifier.

    Returns
    -------
    int, str or None
        Row index, "multiple" if several match, None if none.
    """
    objetivo = identificador.strip()
    coincidencias = [i for i in range(len(df))
                     if _cell(df, i, "Timestamp") == objetivo]
    if not coincidencias:
        return None
    return coincidencias[0] if len(coincidencias) == 1 else "multiple"


def _run_pending(argv, project):
    """
    Dispatch the pending-entry modes (list / all / by id / direct answer).

    Returns
    -------
    int
        Exit code (0 ok, 1 data error, 2 invalid usage).
    """
    ruta_csv = project / "map_data.csv"
    if not ruta_csv.exists():
        print(f"{ruta_csv} does not exist: run update.py before reviewing.")
        return 1
    df = pd.read_csv(ruta_csv)
    pendientes = _pending_indices(df)

    # ---------------- mode 1: no arguments -> oldest pending ----------------
    if not argv:
        if not pendientes:
            print("No entries are pending manual review.")
            return 0
        idx = pendientes[0]                                  # the oldest one
        _print_entry(df, idx, 1, len(pendientes))
        decision = _ask()
        if decision is None:
            print("Entry left pending (nothing was changed).")
            return 0
        veredicto, plan = _apply_decision(df, idx, decision)
        df.to_csv(ruta_csv, index=False)
        print(f'Saved: Aprobado="{veredicto}" -> {plan}.')
        return 0

    # ---------------- mode 2: list ----------------
    if argv[0] == "list":
        if not pendientes:
            print("No entries are pending manual review.")
            return 0
        print(f"Entries pending manual review: {len(pendientes)}\n")
        for posicion, idx in enumerate(pendientes, start=1):
            print(f"{posicion}. Timestamp: {_cell(df, idx, 'Timestamp')!r}   "
                  f"[{posicion}/{len(pendientes)}]")
            print(f"     {_cell(df, idx, 'Nombre del lugar')}  "
                  f"[{_cell(df, idx, 'Campus')} / {_cell(df, idx, 'Edificio')}]")
        print('\nTo review one: python3 review.py "<Timestamp>"')
        return 0

    # ---------------- mode 3: all ----------------
    if argv[0] == "all":
        if not pendientes:
            print("No entries are pending manual review.")
            return 0
        quedan = list(pendientes)
        while quedan:
            idx = quedan[0]
            _print_entry(df, idx, len(pendientes) - len(quedan) + 1, len(pendientes))
            decision = _ask()
            if decision is None:
                print("Entry left pending (nothing was changed). Next.\n")
                quedan.pop(0)
                continue
            veredicto, plan = _apply_decision(df, idx, decision)
            df.to_csv(ruta_csv, index=False)   # saved after EVERY answer
            print(f'Saved: Aprobado="{veredicto}" -> {plan}.\n')
            quedan.pop(0)
        print("End of the review.")
        return 0

    # ---------------- modes 4 and 5: one entry by its identifier ----------------
    idx = _identify(df, argv[0])
    if idx is None or idx == "multiple":
        if idx == "multiple":
            print(f"The identifier {argv[0]!r} matches several entries: "
                  "use `python3 review.py list` to see them.")
        else:
            print(f"No entry with Timestamp {argv[0]!r}. "
                  "Use `python3 review.py list` to see the identifiers.")
        return 1

    if len(argv) >= 2:
        # Mode 5: direct answer, without showing the entry
        decision = _normalise_answer(argv[1])
        if decision is None:
            print(f'Invalid answer: {argv[1]!r} (use "yes" or "no").')
            return 2
    else:
        # Mode 4: show the entry and ask
        _print_entry(df, idx)
        decision = _ask()
        if decision is None:
            print("Entry left pending (nothing was changed).")
            return 0

    veredicto, plan = _apply_decision(df, idx, decision)
    df.to_csv(ruta_csv, index=False)
    print(f'Saved: Aprobado="{veredicto}" -> {plan}.')
    return 0


# %% --------------------------- published points ---------------------------

def _print_point(props, coords, corto_por_largo):
    """
    Print a published point with all its data, aligned.
    """
    print("─" * 58)
    lat = coords[1] if isinstance(coords, list) and len(coords) > 1 else 0.0
    lon = coords[0] if isinstance(coords, list) else 0.0
    tipo = (props.get("tipo") or "")
    tipo_largo = corto_por_largo.get(tipo, "")
    etiquetas = {
        "idnum": props.get("idnum"),
        "name": props.get("nombre"),
        "description": props.get("descrip"),
        "link": props.get("enlace"),
        "type": tipo + (f"  ({tipo_largo})" if tipo_largo else ""),
        "floor": props.get("planta"),
        "building": props.get("edificio"),
        "campus": props.get("campus"),
        "latitude": lat,
        "longitude": lon,
    }
    ancho = max(len(k) for k in etiquetas)
    for clave, valor in etiquetas.items():
        print(f"  {clave:<{ancho}}  {valor if valor not in (None, '') else '(empty)'}")
    print("─" * 58)


def _find_feature(features, idnum):
    """
    Index of the feature with the given idnum (None if absent).

    Returns
    -------
    int or None
        Position in the features list.
    """
    for i, feature in enumerate(features):
        if feature.get("properties", {}).get("idnum") == idnum:
            return i
    return None


def _parse_timestamp(texto):
    """
    Timestamp parser for ordering rows (None if unreadable).
    """
    try:
        return datetime.strptime(str(texto).strip(), "%d/%m/%Y %H:%M:%S")
    except ValueError:
        return None


def _find_source_row(df, props, coords, procesados):
    """
    Find the CSV row that produced a published feature.

    The feature stores coordinates rounded to 6 decimals, so rows are matched
    by proximity (well below the fusion threshold); among several matches the
    base report wins: the oldest row without a "Duplicado de" mark. If the
    feature has no valid coordinates, fall back to a name match.

    Parameters
    ----------
    df : pandas.DataFrame
        The accumulated CSV.
    props : dict
        Feature properties (nombre, planta...).
    coords : list
        Feature coordinates [lon, lat].
    procesados : set of str
        Timestamps already published (log.json).

    Returns
    -------
    int or None
        Row index, or None if it cannot be identified safely.
    """
    lat = coords[1] if isinstance(coords, list) and len(coords) > 1 else 0.0
    lon = coords[0] if isinstance(coords, list) else 0.0
    validas = not (lat == 0 and lon == 0)

    def _candidatos(por):
        """Rows already published that match by coordinates (or by name)."""
        hallados = []
        for i in range(len(df)):
            ts = _cell(df, i, "Timestamp")
            if ts == "(empty)" or ts not in procesados:
                continue                     # only rows behind this feature
            if por == "coords":
                try:
                    dif_lat = abs(float(df.at[i, "Coordenadas: latitud"]) - lat)
                    dif_lon = abs(float(df.at[i, "Coordenadas: longitud"]) - lon)
                except (TypeError, ValueError):
                    continue
                if dif_lat <= _TOL_COORDS and dif_lon <= _TOL_COORDS:
                    hallados.append(i)
            else:
                if _cell(df, i, "Nombre del lugar") == str(props.get("nombre") or ""):
                    hallados.append(i)
        return hallados

    for modo in ("coords", "nombre"):
        if modo == "coords" and not validas:
            continue                          # (0, 0): proximity is useless
        hallados = _candidatos(modo)
        if not hallados:
            continue
        sin_marca = [i for i in hallados
                     if _cell(df, i, "Duplicado de") == "(empty)"]
        # The base report is the oldest unmarked matching row
        pool = sin_marca or hallados
        return min(pool, key=lambda i: (_parse_timestamp(_cell(df, i, "Timestamp"))
                                        or datetime.max))
    return None


def _cmd_point(argv, project):
    """
    Dispatch the published-point modes (show / set / retract).

    Parameters
    ----------
    argv : list of str
        Arguments after "point" (idnum, subcommand...).
    project : Path
        Project folder.

    Returns
    -------
    int
        Exit code (0 ok, 1 data error, 2 invalid usage).
    """
    if not argv:
        print('Usage: python3 review.py point <idnum> [retract [yes] | set <field> <value...>]')
        return 2
    idnum = argv[0]
    ruta_geojson = project / "map_data.geojson"
    geojson = _load_json(ruta_geojson)
    if geojson is None:
        print(f"{ruta_geojson} does not exist or is corrupt: nothing to review.")
        return 1
    features = geojson.get("features", [])
    pos = _find_feature(features, idnum)
    if pos is None:
        print(f"No published point with idnum {idnum!r}.")
        return 1
    feature = features[pos]
    props = feature["properties"]
    coords = feature.get("geometry", {}).get("coordinates", [0.0, 0.0])
    corto_por_largo, _largo = _tipo_maps(project)

    # ---------------- show ----------------
    if len(argv) == 1:
        _print_point(props, coords, corto_por_largo)
        return 0

    # ---------------- retract ----------------
    if argv[1] == "retract":
        return _retract_point(argv[2:], project, geojson, feature, idnum)

    # ---------------- set ----------------
    if argv[1] == "set":
        return _set_point_field(argv[2:], project, geojson, pos, idnum,
                                corto_por_largo)

    print(f"Unknown subcommand {argv[1]!r}: use `retract` or `set`.")
    return 2


def _retract_point(argv, project, geojson, feature, idnum):
    """
    Remove a published point from the map, safely and for good.

    What it does (all together or nothing): safety backup -> remove the
    feature from the working GeoJSON -> flip its source row to "No" (and the
    rows fused into it) -> drop their timestamps from log.json's "procesados"
    -> save. Without publishing anything (the web keeps the old GeoJSON
    until the next update.py).

    Returns
    -------
    int
        Exit code.
    """
    props = feature["properties"]
    features = geojson["features"]
    if len(features) <= 1:
        # Removing the only feature would leave the state inconsistent (an
        # empty GeoJSON with processed rows); the generator guards would
        # abort. The clean way to empty the map is reset.py.
        print("This is the only published point: use reset.py instead "
              "(the generator's coherence guards require it).")
        return 1

    ruta_log = project / "log.json"
    log = _load_json(ruta_log)
    if log is None or "procesados" not in log:
        print(f"{ruta_log} is missing, corrupt or in the old format: "
              "retracting is not safe. Fix the state first (reset.py).")
        return 1
    procesados = set(log.get("procesados", []))

    ruta_csv = project / "map_data.csv"
    if not ruta_csv.exists():
        print(f"{ruta_csv} does not exist: cannot flip the source row. "
              "Run update.py first.")
        return 1
    df = pd.read_csv(ruta_csv)

    coords = feature.get("geometry", {}).get("coordinates", [0.0, 0.0])
    idx_fuente = _find_source_row(df, props, coords, procesados)
    if idx_fuente is None:
        # Without the source row the point could come back after a reset:
        # refuse rather than leave a half-retraction
        print("The source row of this point could not be identified in "
              "map_data.csv (edited coordinates or name?). Nothing was "
              "changed; review the row by hand.")
        return 1
    ts_fuente = _cell(df, idx_fuente, "Timestamp")

    # Every contribution fused into this point: the fusion audit in log.json
    # (by idnum) plus the "Duplicado de" marks in the CSV (belt and braces)
    ts_aportes = {f.get("timestamp") for f in log.get("fusiones", [])
                  if f.get("idnum") == idnum}
    for i in range(len(df)):
        if _cell(df, i, "Duplicado de") == idnum:
            ts_aportes.add(_cell(df, i, "Timestamp"))

    # Show the plan and ask for confirmation ("yes" as an argument skips it)
    print("This will REMOVE the point from the map:")
    _print_point(props, coords, _tipo_maps(project)[0])
    afectadas = [ts_fuente] + sorted(t for t in ts_aportes if t != ts_fuente)
    print(f"Rows flipped to \"No\" (source + contributions): {len(afectadas)}")
    for ts in afectadas:
        fila = next((i for i in range(len(df)) if _cell(df, i, "Timestamp") == ts), None)
        nombre = _cell(df, fila, "Nombre del lugar") if fila is not None else "?"
        print(f"    {ts}  {nombre}")
    confirmado = "yes" in argv
    if not confirmado:
        try:
            confirmado = _normalise_answer(input("Type 'yes' to confirm the removal: ")) == "Sí"
        except EOFError:
            confirmado = False
    if not confirmado:
        print("Cancelled (nothing was changed).")
        return 0

    # 1) Safety backup of everything this operation may touch
    carpeta = _backup(project, ("map_data.geojson", "log.json", "map_data.csv"))
    if carpeta:
        print(f"Backup: {carpeta}")

    # 2) Remove the feature from the working GeoJSON
    features.remove(feature)
    _save_json(project / "map_data.geojson", geojson, indent=2)

    # 3) Flip the affected rows to "No" (a reset must not resurrect them)
    _force_text_columns(df, ("Aprobado",))
    for ts in afectadas:
        fila = next((i for i in range(len(df)) if _cell(df, i, "Timestamp") == ts), None)
        if fila is not None:
            df.at[fila, "Aprobado"] = "No"
    df.to_csv(ruta_csv, index=False)

    # 4) Drop their timestamps from "procesados" (nothing about this point
    #    is published any more); the rest of log.json is preserved verbatim
    log["procesados"] = sorted(procesados - set(afectadas))
    _save_json(ruta_log, log, indent=4)

    print(f"Removed point {idnum} ({props.get('nombre')}) and flipped "
          f"{len(afectadas)} row(s) to \"No\".")
    print("Run commands/update.py to publish the removal to the web.")
    return 0


def _set_point_field(argv, project, geojson, pos, idnum, corto_por_largo):
    """
    Edit one field of a published point (GeoJSON + source CSV row).

    Returns
    -------
    int
        Exit code (0 ok, 1 data error, 2 invalid usage).
    """
    if len(argv) < 2:
        print("Usage: python3 review.py point <idnum> set <field> <value...>")
        print(f"Editable fields: {', '.join(sorted(_SET_FIELDS))}")
        return 2
    campo, valor = argv[0].lower(), " ".join(argv[1:]).strip()
    if campo in _FORBIDDEN_FIELDS:
        print(f"The field {campo!r} cannot be edited: it is part of the "
              "point's identity (idnum) or inferred from the KML (campus, "
              "edificio). Retract the point and re-approve the row instead.")
        return 2
    if campo not in _SET_FIELDS:
        print(f"Unknown field {campo!r}. Editable fields: "
              f"{', '.join(sorted(_SET_FIELDS))}")
        return 2
    if not valor:
        print("The value cannot be empty.")
        return 2

    feature = geojson["features"][pos]
    props = feature["properties"]
    coords = feature.get("geometry", {}).get("coordinates", [0.0, 0.0])
    prop_nombre, columna_csv = _SET_FIELDS[campo]

    # Validate and translate the value per field
    nuevo_csv = valor
    if campo == "type":
        # Accept the long type name or the short code; the GeoJSON stores the
        # short code and the CSV the long name
        if valor in corto_por_largo:
            pass                             # long name given: as is
        elif valor in _tipo_maps(project)[1]:
            nuevo_csv = _tipo_maps(project)[1][valor]   # short -> long
        else:
            print(f"Unknown type {valor!r}. Valid long names:")
            for largo in corto_por_largo:
                print(f"    {largo}  (code: {corto_por_largo[largo]})")
            return 2
    if campo in ("latitude", "longitude"):
        try:
            valor_num = round(float(valor), 6)
        except ValueError:
            print(f"{valor!r} is not a number.")
            return 2

    # Locate the source row BEFORE editing (so the match uses the old values)
    ruta_csv = project / "map_data.csv"
    df = pd.read_csv(ruta_csv) if ruta_csv.exists() else None
    log = _load_json(project / "log.json")
    idx_fuente = None
    if df is not None and log is not None and "procesados" in log:
        idx_fuente = _find_source_row(df, props, coords, set(log["procesados"]))

    # Safety backup of everything this operation may touch
    carpeta = _backup(project, ("map_data.geojson", "map_data.csv"))
    if carpeta:
        print(f"Backup: {carpeta}")

    # 1) The working GeoJSON is the source of truth: edit the feature
    viejo = None
    if campo == "latitude":
        viejo, nuevo = coords[1], valor_num
        coords[1] = valor_num
    elif campo == "longitude":
        viejo, nuevo = coords[0], valor_num
        coords[0] = valor_num
    else:
        viejo = props.get(prop_nombre)
        if prop_nombre == "tipo":
            # GeoJSON stores the SHORT code (the CSV keeps the long name)
            nuevo = corto_por_largo.get(nuevo_csv, nuevo_csv)
        elif prop_nombre == "planta" and campo == "floor":
            # Same transformation the generator applies: Baja/Sótano in
            # lower case, otherwise the last token ("Planta 1" -> "1")
            if nuevo_csv in ("Baja", "Sótano"):
                nuevo = nuevo_csv.lower()
            elif nuevo_csv.split():
                nuevo = nuevo_csv.split()[-1]
            else:
                nuevo = ""
        else:
            nuevo = valor
        props[prop_nombre] = nuevo
    _save_json(project / "map_data.geojson", geojson, indent=2)
    print(f"Point {idnum}: {campo}  {viejo!r} -> {nuevo!r}")
    if campo in ("latitude", "longitude"):
        print("Note: campus and building are NOT re-inferred; if the point "
              "moved to another building, retract it and re-approve the row.")

    # 2) Mirror the change into the source row, so a reset cannot lose it
    if df is not None and idx_fuente is not None:
        _force_text_columns(df, (columna_csv,))
        if campo in ("latitude", "longitude"):
            df.at[idx_fuente, columna_csv] = valor_num
        else:
            df.at[idx_fuente, columna_csv] = nuevo_csv
        df.to_csv(ruta_csv, index=False)
        print(f"Source row updated in map_data.csv "
              f"(Timestamp {_cell(df, idx_fuente, 'Timestamp')}).")
    else:
        print("Warning: source row not found in map_data.csv; the CSV was "
              "not updated (a reset would lose this change).")

    print("Run commands/update.py to publish the change to the web.")
    return 0


# %% ------------------------------- entry point -------------------------------

_USO = (
    "usage: python3 review.py                       -> oldest pending entry (show + ask)\n"
    "       python3 review.py list                  -> list every pending entry\n"
    "       python3 review.py all                   -> review all pending, one by one\n"
    '       python3 review.py "<timestamp>"          -> show that entry and ask\n'
    '       python3 review.py "<timestamp>" yes|no   -> answer directly (without showing)\n'
    "       python3 review.py point <idnum>          -> show a published point\n"
    "       python3 review.py point <idnum> retract [yes]  -> remove it from the map\n"
    "       python3 review.py point <idnum> set <field> <value...>  -> edit one field\n"
    "             fields: name, description, link, type, floor (alias plant), latitude, longitude"
)


def _main(argv):
    """
    Entry point: dispatch by the arguments received.

    Parameters
    ----------
    argv : list of str
        Command-line arguments (without the program name).

    Returns
    -------
    int
        Exit code (0 ok, 1 data error, 2 invalid usage).
    """
    if any(a in ("-h", "--help") for a in argv):
        print(_USO)
        return 0
    project = _project_dir()
    if argv and argv[0] == "point":
        return _cmd_point(argv[1:], project)
    return _run_pending(argv, project)


def main():
    """Wrapper around _main that returns the exit code to the console."""
    return _main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
