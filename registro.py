# registro.py — Configuración compartida, registro exhaustivo y utilidades de despliegue (GadirE).
#
# Módulo común de todos los scripts de operación (update.py, reset.py,
# calendario.py, cron.py, estado.py). Reúne en un solo sitio:
#   1. Las rutas y URLs del proyecto (sobrescribibles con variables de
#      entorno GADIRE_* para poder probar todo sin tocar el servidor).
#   2. El registro (log) exhaustivo de cada ejecución: consola +
#      logs/<programa>_<fecha>.log (uno por ejecución, no se borra nunca) +
#      logs/ultimo.log (siempre la última ejecución, para tail -f).
#   3. Las utilidades compartidas: descarga atómica con validación (nunca
#      deja un archivo a medias si la descarga falla), publicación en la
#      web con permisos correctos, bloqueo contra ejecuciones solapadas y
#      ejecución en vivo de los programas del pipeline (adecuacion.py,
#      generador_map_data.py) volcando su salida al log línea a línea.
#
# Nunca se importa desde adecuacion.py ni generador_map_data.py: ellos son
# programas independientes; este módulo es de los orquestadores.

import fcntl
import logging
import os
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

# %%
# ----------------------------- Configuración -----------------------------
# Directorio base: donde vive este archivo (los scripts funcionan aunque se
# ejecuten desde cualquier otra carpeta).
BASE_DIR = Path(__file__).resolve().parent

# Carpeta del proyecto: por defecto la del propio script (en el servidor es el
# clon de ~/generador_geojson_gadire). Sobrescribible con GADIRE_RUTA_PROYECTO.
RUTA_PROYECTO = Path(os.environ.get("GADIRE_RUTA_PROYECTO", str(BASE_DIR)))

# Carpeta servida por nginx (¡Gadire con mayúsculas! Linux distingue mayúsculas
# y minúsculas en las rutas). Sobrescribible con GADIRE_RUTA_WEB (para pruebas).
RUTA_WEB = Path(os.environ.get("GADIRE_RUTA_WEB", "/var/www/Gadire/data"))

# CSV publicado del formulario de Google (File → Share → Publish to web, CSV).
URL_CSV = os.environ.get(
    "GADIRE_URL_CSV",
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vThD440g6SWeHwrzyPWSd5VdDBaJpZViRe1aAhI8CjdsH7EYHJYaAszl_G-Spp1sFhYToGSBaA7736U/pub?output=csv",
)
NOMBRE_CSV = "map_data_form.csv"

# Calendario ICS público de la Presidencia del CEUCA.
URL_ICS = os.environ.get(
    "GADIRE_URL_ICS",
    "https://calendar.google.com/calendar/ical/c_bace818e910e006dac3bc75e9848c4c85b14d373f7ebbca58e75253af719351c%40group.calendar.google.com/public/basic.ics",
)
NOMBRE_ICS = "agenda_publica_presidencia_CEUCA.ics"

# Carpeta de logs (dentro del proyecto). Sobrescribible con GADIRE_RUTA_LOGS.
RUTA_LOGS = Path(os.environ.get("GADIRE_RUTA_LOGS", str(RUTA_PROYECTO / "logs")))

# %%
# --------------------------- Registro (logging) ---------------------------

def configurar_log(nombre_programa):
    """
    Crea el logger de una ejecución: consola + un archivo por ejecución +
    logs/ultimo.log con la última.

    Parameters
    ----------
    nombre_programa : str
        Nombre del script que registra (update, reset, calendario...).
        Aparece en el nombre del archivo de log.

    Returns
    -------
    tuple of (logging.Logger, Path)
        El logger configurado y la ruta del archivo de log de esta ejecución.
    """
    RUTA_LOGS.mkdir(parents=True, exist_ok=True)          # logs/ se crea si faltara
    fecha = time.strftime("%Y%m%d_%H%M%S")
    ruta_log = RUTA_LOGS / f"{nombre_programa}_{fecha}.log"

    # Logger propio de esta ejecución (nombre único: no hereda handlers de otras)
    logger = logging.getLogger(f"gadire.{nombre_programa}.{fecha}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formato = logging.Formatter("[%(asctime)s] %(message)s", "%Y-%m-%d %H:%M:%S")

    # Tres destinos: consola, archivo de esta ejecución y ultimo.log
    consola = logging.StreamHandler(sys.stdout)
    consola.setFormatter(formato)
    archivo = logging.FileHandler(ruta_log, encoding="utf-8")      # se conserva SIEMPRE
    archivo.setFormatter(formato)
    ultimo = logging.FileHandler(RUTA_LOGS / "ultimo.log", mode="w", encoding="utf-8")
    ultimo.setFormatter(formato)
    for manejador in (consola, archivo, ultimo):
        logger.addHandler(manejador)

    logger.info("=== %s — inicio (log completo en %s) ===", nombre_programa, ruta_log)
    return logger, ruta_log


@contextmanager
def bloquear(logger):
    """
    Bloqueo contra ejecuciones solapadas (p. ej. cron + update.py a la vez).

    Parameters
    ----------
    logger : logging.Logger
        Logger donde se avisa si la ejecución se queda esperando.

    Yields
    ------
    None
        El bloqueo se libera solo al salir del `with`.
    """
    RUTA_LOGS.mkdir(parents=True, exist_ok=True)
    ruta_bloqueo = RUTA_LOGS / ".bloqueo"
    # Lock exclusivo no bloqueante: si otro proceso lo tiene, aborta
    with open(ruta_bloqueo, "w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise SystemExit("Ya hay otra ejecución en marcha (logs/.bloqueo tomado): se aborta esta.")
        logger.info("Bloqueo adquirido (logs/.bloqueo)")
        try:
            yield
        finally:
            # Al soltar: el flock se libera al cerrar el archivo (aquí, explícito)
            fcntl.flock(f, fcntl.LOCK_UN)
            logger.info("Bloqueo liberado")

# %%
# ---------------------- Descargas y validación atómica ----------------------

def validar_csv_formulario(datos):
    """
    Valida que los bytes descargados sean el CSV del formulario (cabecera con
    las columnas clave) antes de dejar que pisen el archivo anterior.

    Parameters
    ----------
    datos : bytes
        Contenido descargado.

    Raises
    ------
    ValueError
        Si la cabecera no contiene las columnas esperadas.
    """
    texto = datos.decode("utf-8-sig", errors="replace")   # utf-8-sig: quita BOM si lo hay
    cabecera = texto.splitlines()[0] if texto.splitlines() else ""
    # Las dos columnas sin las que el pipeline no funciona
    if "Timestamp" not in cabecera or "Nombre del lugar" not in cabecera:
        raise ValueError(f"El CSV descargado no parece el del formulario (cabecera: {cabecera[:120]!r})")


def validar_ics(datos):
    """
    Valida que los bytes descargados sean un calendario ICS.

    Parameters
    ----------
    datos : bytes
        Contenido descargado.

    Raises
    ------
    ValueError
        Si no contiene BEGIN:VCALENDAR (Google devuelve HTML si la URL falla).
    """
    if b"BEGIN:VCALENDAR" not in datos:
        raise ValueError("Lo descargado no es un ICS válido (sin BEGIN:VCALENDAR): no se publica")


def descargar(url, destino, logger, validador=None, intentos=3):
    """
    Descarga una URL a un archivo de forma ATÓMICA: se baja a un .tmp, se
    valida y solo entonces sustituye al destino (os.replace). Si la descarga
    o la validación fallan, el archivo anterior queda intacto.

    Parameters
    ----------
    url : str
        URL a descargar.
    destino : Path
        Ruta final del archivo (se sobrescribe solo si todo va bien).
    logger : logging.Logger
        Logger de la ejecución.
    validador : callable, optional
        Función que recibe los bytes y lanza ValueError si el contenido no
        es válido (p. ej. validar_csv_formulario).
    intentos : int, optional
        Número de intentos ante fallos de red (por defecto 3).

    Returns
    -------
    int
        Tamaño en bytes del archivo descargado.
    """
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    ultima_exc = None
    for intento in range(1, intentos + 1):
        try:
            logger.info("Descargando %s (intento %d/%d)", url, intento, intentos)
            # User-Agent explícito: algunos servidores rechazan el de urllib
            peticion = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (GadirE)"})
            with urllib.request.urlopen(peticion, timeout=120) as respuesta:
                datos = respuesta.read()
            if not datos:
                raise ValueError("Descarga vacía (0 bytes)")
            # Validación ANTES de tocar el destino: contenido malo no se publica
            if validador is not None:
                validador(datos)
            tmp = destino.parent / (destino.name + ".tmp")
            tmp.write_bytes(datos)
            os.replace(tmp, destino)      # atómico: o el viejo o el nuevo, nunca un híbrido
            logger.info("Descargado y validado: %s (%d bytes)", destino, len(datos))
            return len(datos)
        except Exception as exc:          # red, timeout, validación: se reintenta
            ultima_exc = exc
            logger.warning("Fallo en el intento %d: %s", intento, exc)
            if intento < intentos:
                time.sleep(5)            # pequeña espera antes de reintentar
    raise RuntimeError(f"No se pudo descargar {url} tras {intentos} intentos: {ultima_exc}")

# %%
# ------------------------- Publicación en la web -------------------------

def ajustar_permisos_web(ruta, logger):
    """
    Deja un archivo publicado legible por nginx: chmod 644 y propietario
    www-data (si el usuario actual puede, p. ej. root).

    Parameters
    ----------
    ruta : Path
        Archivo publicado.
    logger : logging.Logger
        Logger de la ejecución.
    """
    try:
        os.chmod(ruta, 0o644)
    except PermissionError:
        logger.warning("Sin permisos para chmod %s (¿ejecutando sin sudo?)", ruta)
    try:
        import pwd                      # Unix: sólo disponible en Linux
        usuario = pwd.getpwnam("www-data")
        os.chown(ruta, usuario.pw_uid, usuario.pw_gid)
    except (ImportError, KeyError):
        # Sin pwd (pruebas) o sin usuario www-data: se deja el propietario actual
        logger.info("Propietario sin cambiar (no hay www-data en este sistema)")
    except PermissionError:
        logger.warning("Sin permisos para chown %s (¿ejecutando sin sudo?)", ruta)


def publicar(origen, destino, logger):
    """
    Copia un archivo a la carpeta web de forma atómica y con permisos.

    Parameters
    ----------
    origen : Path
        Archivo generado (p. ej. map_data.geojson del proyecto).
    destino : Path
        Ruta servida (p. ej. /var/www/Gadire/data/map_data.geojson).
    logger : logging.Logger
        Logger de la ejecución.
    """
    origen, destino = Path(origen), Path(destino)
    datos = origen.read_bytes()
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.parent / (destino.name + ".tmp")
    tmp.write_bytes(datos)
    os.replace(tmp, destino)             # atómico: la web nunca sirve un archivo a medias
    ajustar_permisos_web(destino, logger)
    logger.info("Publicado: %s (%d bytes)", destino, len(datos))

# %%
# --------------------------- Pipeline compartido ---------------------------

def ejecutar_programa(programa, logger, env_extra=None):
    """
    Ejecuta un programa del pipeline (adecuacion.py, generador_map_data.py)
    en vivo: cada línea de su salida se registra al momento (para poder
    hacer tail -f durante ejecuciones largas).

    Parameters
    ----------
    programa : str
        Nombre del script (en la raíz del proyecto).
    logger : logging.Logger
        Logger donde se vuelca la salida.
    env_extra : dict, optional
        Variables de entorno adicionales (GADIRE_MODO, ...).

    Returns
    -------
    str
        Última línea RESUMEN_* que emitió el programa ('' si no emitió).
    """
    env = os.environ.copy()
    env.update(env_extra or {})
    logger.info("== Ejecutando %s ==", programa)
    inicio = time.time()
    # stdout y stderr juntos: los tracebacks también quedan en el log, en orden
    proceso = subprocess.Popen(
        [sys.executable, str(RUTA_PROYECTO / programa)],
        cwd=str(RUTA_PROYECTO),          # los programas usan rutas relativas
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    resumen = ""
    for linea in proceso.stdout:        # en vivo: línea a línea, sin esperar al final
        linea = linea.rstrip()
        logger.info("[%s] %s", programa, linea)
        if linea.startswith("RESUMEN_"):
            resumen = linea              # se queda con la última línea RESUMEN_*
    codigo = proceso.wait()
    if codigo != 0:
        raise RuntimeError(f"{programa} falló con código de salida {codigo} (detalle arriba, en el log)")
    logger.info("== %s terminado correctamente (%.1f s) ==", programa, time.time() - inicio)
    return resumen


def ejecutar_pipeline(logger, modo):
    """
    Pipeline completo de actualización del mapa: descarga del CSV del
    formulario → adecuacion.py (moderación) → generador_map_data.py
    (incremental + dedup) → publicación en la web.

    Parameters
    ----------
    logger : logging.Logger
        Logger de la ejecución.
    modo : str
        'update' (incremental) o 'reset' (regeneración completa): se le pasa
        al generador para que quede grabado en log.json (auditoría).

    Returns
    -------
    str
        Línea RESUMEN_GENERADOR del generador (recuento final).
    """
    inicio = time.time()
    logger.info("=== %s: descargando el CSV del formulario ===", modo.upper())
    descargar(URL_CSV, RUTA_PROYECTO / NOMBRE_CSV, logger, validador=validar_csv_formulario)

    # Moderación: su línea RESUMEN_ADECUACION lleva las estadísticas de esta pasada
    resumen_adec = ejecutar_programa("adecuacion.py", logger)

    # El resumen de la moderación viaja al generador por variable de entorno:
    # así log.json guarda la ejecución COMPLETA en un solo sitio (auditoría)
    env_gen = {"GADIRE_MODO": modo}
    if " " in resumen_adec:
        env_gen["GADIRE_RESUMEN_ADECUACION"] = resumen_adec.split(" ", 1)[1]

    resumen_gen = ejecutar_programa("generador_map_data.py", logger, env_gen)

    # Publicación: sólo si todo lo anterior ha ido bien
    publicar(RUTA_PROYECTO / "map_data.geojson", RUTA_WEB / "map_data.geojson", logger)
    logger.info("=== %s completado (%.1f s) === %s", modo.upper(), time.time() - inicio, resumen_gen)
    return resumen_gen
