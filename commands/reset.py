# reset.py — Reset del mapa: borrar el estado y reconstruir TODO desde el CSV.
#
# El reset es el nombre definitivo de lo que antes se llamaba "regeneración
# completa": borra log.json y map_data.geojson (SIEMPRE juntos) y reconstruye
# el mapa entero desde el CSV del formulario. map_data.csv NO se toca: guarda
# los veredictos y aprobaciones manuales, y la moderación los reutiliza.
#
# Es sano (purga features fantasma y recupera filas víctimas de bugs viejos),
# pero sólo se hace a propósito: el mantenimiento normal es update.py.
#
# Por seguridad pide confirmación escribiendo EXACTAMENTE "GadirE" (con las
# mayúsculas). Los archivos de estado no se destruyen: se guardan en
# backups/<fecha>/ antes de regenerar (se pueden restaurar a mano si hiciera
# falta).

import time

import os
import sys

# The shared engine (pipeline.py) lives in commands/scripts/, one level below
# this file: adding it to sys.path lets every entry point import it with the
# same name, so the body below can keep using `registro` as always.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts"))

import pipeline as registro

# Los dos archivos de estado que hay que borrar SIEMPRE juntos (nunca uno solo)
ARCHIVOS_ESTADO = ("log.json", "map_data.geojson")


def main():
    """
    Pide confirmación, respalda y borra el estado, y reconstruye el mapa.

    Returns
    -------
    int
        0 si el reset se completó, 1 si se canceló o falló.
    """
    # Confirmación interactiva ANTES de tocar nada (el reset no es rutina)
    print("RESET del mapa: se borraran log.json y map_data.geojson (juntos)")
    print("y se reconstruira TODO desde el CSV del formulario.")
    print("map_data.csv NO se toca (conserva los veredictos manuales).")
    try:
        respuesta = input('Escribe exactamente "GadirE" para confirmar: ')
    except EOFError:
        # Entrada cerrada (p. ej. ejecutado sin terminal): no hay confirmación
        print("No se pudo leer la confirmacion: reset cancelado.")
        return 1
    if respuesta != "GadirE":
        print('Confirmacion incorrecta: reset CANCELADO (no se ha tocado nada).')
        return 1

    logger, _ruta_log = registro.configurar_log("reset")
    try:
        with registro.bloquear(logger):
            inicio = time.time()

            # 1) Respaldo y borrado JUNTOS: mover a backups/ es atomico por
            #    archivo y equivale a borrarlos de la carpeta de trabajo
            #    (con la ventaja de conservar una copia por si acaso)
            carpeta_backup = registro.RUTA_PROYECTO / "backups" / time.strftime("%Y%m%d_%H%M%S")
            movidos = []
            try:
                for nombre in ARCHIVOS_ESTADO:
                    origen = registro.RUTA_PROYECTO / nombre
                    if origen.exists():
                        carpeta_backup.mkdir(parents=True, exist_ok=True)
                        os.replace(origen, carpeta_backup / nombre)
                        movidos.append(nombre)
                        logger.info("Respaldo (y borrado) de %s -> %s", nombre, carpeta_backup / nombre)
            except Exception:
                # Si falla a mitad (p. ej. permisos), se restaura lo movido:
                # jamas queda un estado a medias (uno borrado y otro no)
                logger.error("Fallo moviendo el estado: restaurando lo ya movido...")
                for nombre in movidos:
                    os.replace(carpeta_backup / nombre, registro.RUTA_PROYECTO / nombre)
                raise
            if movidos:
                logger.info("Estado borrado (respaldado): %s", ", ".join(movidos))
            else:
                logger.info("No habia archivos de estado: arranque en frio (no hay nada que borrar)")

            # 2) Pipeline completo en modo reset: descarga CSV -> moderacion ->
            #    generador (sin log.json arranca de cero) -> publicacion
            registro.ejecutar_pipeline(logger, "reset")
            logger.info("=== RESET completado (%.1f s); respaldo en %s ===",
                        time.time() - inicio, carpeta_backup if movidos else "(no habia estado)")
        return 0
    except SystemExit:
        raise
    except PermissionError:
        logger.exception("=== RESET: FALLO de permisos (prueba con sudo) ===")
        return 1
    except Exception:
        logger.exception("=== RESET: FALLO (el estado esta respaldado en backups/) ===")
        return 1


if __name__ == "__main__":
    sys.exit(main())
