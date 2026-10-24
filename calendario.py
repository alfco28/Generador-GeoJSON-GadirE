# calendario.py — Actualización del calendario ICS de la Presidencia del CEUCA.
#
# Descarga el ICS público del calendario de Google y lo publica en la web
# (RUTA_WEB = /var/www/Gadire/data, ¡con G mayúscula!). La descarga es atómica
# y validada: si Google falla o devuelve basura, el ICS servido queda intacto.
#
# (Este script sustituye a actualiza_calendario_pre_ceuca.sh, que apuntaba a
# /var/www/gadire/data en minúsculas: en Linux las mayúsculas importan, así
# que wget fallaba a diario y el ICS publicado llevaba sin actualizarse desde
# que se copió a mano.)

import sys

import registro


def main():
    """
    Descarga y publica el ICS del calendario de forma atómica.

    Returns
    -------
    int
        0 si se publicó, 1 si falló (el ICS servido queda intacto).
    """
    logger, _ruta_log = registro.configurar_log("calendario")
    try:
        destino = registro.RUTA_WEB / registro.NOMBRE_ICS
        # Descarga atómica con validación de contenido ICS
        registro.descargar(registro.URL_ICS, destino, logger, validador=registro.validar_ics)
        registro.ajustar_permisos_web(destino, logger)
        logger.info("=== CALENDARIO actualizado: %s (%d bytes) ===", destino, destino.stat().st_size)
        return 0
    except Exception:
        logger.exception("=== CALENDARIO: FALLO (el ICS servido queda intacto) ===")
        return 1


if __name__ == "__main__":
    sys.exit(main())
