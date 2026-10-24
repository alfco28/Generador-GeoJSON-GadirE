# update.py — Actualización incremental del mapa (lo que hace el cron, a mano).
#
# Ejecuta el pipeline completo SIN reset: descarga el CSV del formulario
# (atómica y validada), lo modera (moderation.py, con Ollama), genera los
# features nuevos fusionando los duplicados (generate_geojson.py) y publica
# map_data.geojson en la web. Si cualquier paso falla, se aborta ANTES de
# publicar: la web conserva el último GeoJSON bueno.
#
# Uso (con el venv o con el python3 del venv directamente, desde la raíz):
#     python3 commands/update.py
#     sudo python3 commands/update.py   # con sudo si toca archivos de root
# (el cron no llama a este archivo directamente: llama a cron.py mapa)

import os
import sys

# The shared engine (pipeline.py) lives in commands/scripts/, one level below
# this file: adding it to sys.path lets every entry point import it with the
# same name, so the body below can keep using `registro` as always.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))

import pipeline as registro


def main():
    """
    Orquesta una actualización incremental y devuelve el código de salida.

    Returns
    -------
    int
        0 si todo fue bien, 1 si falló (con el detalle en el log).
    """
    logger, _ruta_log = registro.configurar_log("update")
    try:
        # El bloqueo evita pisarse con otro update/reset simultáneo
        with registro.bloquear(logger):
            registro.ejecutar_pipeline(logger, "update")
        return 0
    except SystemExit:
        # bloquear() aborta si ya hay otra ejecución: se propaga tal cual
        raise
    except Exception:
        # logger.exception registra el traceback COMPLETO en el log
        logger.exception("=== UPDATE: FALLO (no se ha publicado nada nuevo) ===")
        return 1


if __name__ == "__main__":
    sys.exit(main())
