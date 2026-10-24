# cron.py — Punto de entrada único para el cron del servidor.
#
# El crontab llama SIEMPRE a este archivo, nunca a los otros directamente:
#     python3 cron.py mapa        -> update.py (pipeline del mapa, incremental)
#     python3 cron.py calendario  -> ics.py (ICS de la Presidencia)
#     python3 cron.py todo        -> los dos, en orden
#
# Así el crontab no cambia aunque se añadan pasos, y todo pasa por el mismo
# registro (logs/) y el mismo bloqueo contra ejecuciones solapadas.

import sys

# Tareas válidas del cron (mapa = lunes a viernes 04:00; calendario = a diario 04:30)
TAREAS = ("mapa", "calendario", "todo")


def main(argv):
    """
    Ejecuta la tarea pedida y devuelve el peor código de salida.

    Parameters
    ----------
    argv : list of str
        Argumentos de línea de comandos; argv[1] es la tarea.

    Returns
    -------
    int
        0 si toda la tarea fue bien, 1/2 si algo falló.
    """
    if len(argv) != 2 or argv[1] not in TAREAS:
        print(f"uso: python3 {argv[0]} {'|'.join(TAREAS)}")
        return 2

    # Import perezoso: sólo se carga lo que la tarea necesita
    codigo_salida = 0
    if argv[1] in ("mapa", "todo"):
        import update
        codigo_salida = max(codigo_salida, update.main())
    if argv[1] in ("calendario", "todo"):
        import ics
        codigo_salida = max(codigo_salida, ics.main())
    return codigo_salida


if __name__ == "__main__":
    sys.exit(main(sys.argv))
