# Deduplicación con fusión aditiva

Los usuarios del formulario reportan a veces puntos que **ya están en el mapa** (o que ya reportó otra persona en el mismo lote). Desde v13 (24-10-2026), el backend no crea una feature nueva en ese caso: **añade** la información nueva a la feature existente. Esta política es *aditiva*: nunca se suprime ni se sustituye nada de lo ya publicado, y el `idnum` de la feature existente **jamás cambia** (el frontend depende de su estabilidad).

El módulo `dedup.py` reúne todas las reglas de detección para que `adecuacion.py` y `generador_map_data.py` decidan igual. Ninguna regla compara **solo por nombre**: "FC2" y "FC4" son aulas distintas aunque se parezcan.

## Reglas de detección

Los candidatos se filtran antes de compararse: en `generador_map_data.py` por **campus + edificio** (grupo) y planta; en `adecuacion.py` por planta (sus candidatas son las features publicadas y las filas ya aprobadas del lote). **Planta distinta = lugar distinto.** Una planta vacía en el reporte casa con cualquier cosa (sin planta no hay evidencia de ser otra planta).

Con los candidatos filtrados, se aplican por orden:

| Regla | Qué compara | Notas |
|---|---|---|
| **R1** | Nombre exacto tras normalizar (unidecode + minúsculas + sin puntuación) | "Cafetería del CASEM" ≠ "Cafeteria CASEM" en R1, pero R1 cubre los reportes literales repetidos. |
| **R2** | Nombres *parecidos*: longitud ≥ 8 caracteres Y (similitud Levenshtein ≥ 0,8 o un nombre es subconjunto de tokens del otro, ignorando conectores como "de", "del", "la"...) | "Cafetería CASEM" ⊆ "Cafetería del CASEM" → casan. Los nombres cortos ("FC2", "FC4") solo pueden casar por R1. |
| **R3** | Consulta semántica al LLM (`mistral:7b`), solo en `adecuacion.py` y solo con candidatos ambiguos: misma planta, coordenadas a menos de 50 m y nombre que NO casa por R1/R2 | Una llamada corta por candidata, de más cerca a más lejos. Ante cualquier duda o fallo: no fusionar. |

**Guardia de dígitos (v14):** si los nombres contienen **números distintos**, R2 no aplica: "Aula FC2" y "Aula FC4" miden 8 caracteres (pasan el filtro de longitud) y casaban por similitud con coordenadas cercanas, fundiendo aulas distintas. Los dígitos de un nombre son su identificador: con números diferentes no hay fusión por parecido.

**Confirmación por coordenadas:** cuando ambos puntos tienen coordenadas válidas, la fusión solo procede si distan **≤ 50 m** (`UMBRAL_METROS`; ajustado con datos reales: los dos "Cuarto de baño" de la Facultad de Ciencias distan 57,7 m y deben quedar separados; las dos salas de estudio de la FC distan 5 m y son la misma). Si casan por nombre pero distan más, **no se fusionan** y se emite un **aviso** (registrado en `log.json`): son sitios distintos con nombre coincidente. Coordenadas ausentes (0, 0) cuentan como compatibles con todo.

## Marca "Duplicado de"

Cuando `adecuacion.py` detecta el duplicado, lo escribe en la columna **`Duplicado de`** de `map_data.csv` (solo ahí: **el CSV del formulario nunca se edita**, la siguiente descarga lo pisaría). El valor es el `idnum` de la feature publicada gemela o el `Timestamp` de la gemelo del mismo lote; además copia el tipo del gemelo, ahorrándose la llamada LLM de clasificación.

`generador_map_data.py` resuelve la marca y la **verifica siempre contra el grupo** (campus + edificio + planta): una marca que apunte a un gemelo de otro campus/edificio/planta se ignora (y queda registrado el motivo), así que una marca corrupta nunca puede fusionar puntos que no sean del mismo sitio.

## Política de fusión campo a campo

Al fusionar, la feature existente se muta **in situ** (los índices internos ven siempre el estado vigente):

| Campo | Política |
|---|---|
| `descrip` | Se **añade** el texto nuevo al final (separado por espacio), solo si aporta información que no está ya contenida (comparación normalizada). |
| `enlace` | Solo se **rellena** si estaba vacío. Si ambos están llenos y difieren: **conflicto** — se mantiene el existente y el nuevo queda registrado en `log.json` para revisión manual. |
| `tipo` | Solo se rellena si estaba vacío o `"Desconocido"` (el `idnum` codifica el tipo: nunca cambia). Un tipo distinto queda como conflicto en `log.json`. |
| Coordenadas | Solo se rellenan si la feature estaba en (0, 0). |
| `nombre` | **No cambia** (el nuevo nombre queda como `alias` en la auditoría de la fusión). |
| `planta`, `edificio`, `campus`, `idnum` | **No cambian nunca.** |

El Timestamp de la fila fusionada queda marcado como procesado (no vuelve a examinarse).

## Dónde actúa y con quién

- **`adecuacion.py`** detecta duplicados contra las features **publicadas** (`map_data.geojson`) y contra las filas aprobadas del **mismo lote**. Lo detectado escribe la marca y copia el tipo sin gasto de LLM.
- **`generador_map_data.py`** aplica la fusión: resuelve la marca (verificando el grupo) y, si no hay marca, repite la detección barata R1/R2 entre las features del grupo (publicadas o recién creadas en esta ejecución).
- **Reset**: sin features publicadas previas, todos los duplicados del CSV se resuelven dentro del propio lote, en orden cronológico (la feature base de cada lugar es su primer reporte). El resultado del reset es idéntico a lo que el incremental habría ido publicando.

## Auditoría en log.json

Todo queda registrado para poder depurar y auditar:

- **`fusiones`** (lista): una entrada por fusión, con `timestamp` del aporte, `idnum` de la feature receptora, `campos_actualizados`, `alias` (si el nombre nuevo difería) y `conflictos` (si los hubo).
- **`avisos_duplicados`** (lista): coincidencias por nombre descartadas por distancia, con `timestamp`, `idnum_existente` y `distancia_m`. Un mismo aviso (mismo timestamp + idnum) no se registra dos veces.
- **`ejecuciones`** (lista, v14): cada ejecución lleva sus fusiones y avisos propios, junto con los contadores completos de esa pasada.

Las fusiones y avisos también se imprimen por consola durante la ejecución, y quedan en el log de la misma (`logs/`).
