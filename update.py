# update.py — Actualización incremental del mapa (lo que hace el cron, a mano).
#
# Ejecuta el pipeline completo SIN reset: descarga el CSV del formulario
# (atómica y validada), lo modera (adecuacion.py, con Ollama), genera los
# features nuevos fusionando los duplicados (generador_map_data.py) y publica
# map_data.geojson en la web. Si cualquier paso falla, se aborta ANTES de
# publicar: la web conserva el último GeoJSON bueno.
#
# Uso (en el servidor, con el venv o con el python3 del venv directamente):
#     python3 update.py            # desde la carpeta del proyecto
#     sudo python3 update.py       # con sudo si toca archivos de root
# (el cron no llama a este archivo directamente: llama a cron.py mapa)

import sys

import registro


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
