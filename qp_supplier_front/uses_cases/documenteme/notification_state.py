# -*- coding: utf-8 -*-
"""
notification_state.py (documenteme)
===================================
Nucleo puro del estado de notificacion documenteme (`nvfac_ueve`).

Modelo
------
- PENDIENTES ("en cola"): vacio/None, "030", "032". Entran al flujo
  (asignacion, promocion a V, aprobacion automatica, rechazo automatico,
  receipt trigger) igual que las facturas sin evento.
- FINALES: "031" (rechazado), "033" (aprobado). Se registran y se muestran en
  el portal, pero no entran al flujo automatico.
- DESCONOCIDO: no entra al flujo automatico (conservador), pero se conserva.

Sin imports a Frappe: funciones puras y testables en aislamiento.
El estado final de origen (`A`/`R` o ueve `031`/`033`) siempre manda; un
origen intermedio (`030`/`032`) nunca degrada un estado local avanzado.
"""

PENDING_CODES = ("", "030", "032")
FINAL_CODES = ("031", "033")
KNOWN_CODES = ("030", "031", "032", "033")

# Estado local final que corresponde a cada evento final de documenteme.
FINAL_STATE_BY_CODE = {
    "033": "A",
    "031": "R",
}

# Estados locales que ya avanzaron el flujo propio (creacion en BC, proceso,
# final, asignaciones especiales) y no deben retroceder ante un origen
# intermedio. El re-sync solo los toca si el origen es final.
ADVANCED_STATES = ("SO", "SR", "PSA", "BCC", "PA", "A", "R")


def normalize(value):
    """Normaliza un ueve a string sin espacios (None/vacio -> "")."""
    if value is None:
        return ""
    return str(value).strip()


def is_pending(value):
    """True si el ueve es "en cola" (vacio, 030 o 032)."""
    return normalize(value) in PENDING_CODES


def is_final(value):
    """True si el ueve es final (031 rechazado o 033 aprobado)."""
    return normalize(value) in FINAL_CODES


def is_known(value):
    """True si el ueve es un codigo conocido de documenteme."""
    return normalize(value) in KNOWN_CODES


def resolve_state(current_state, origin_state, origin_ueve,
                  advanced_states=ADVANCED_STATES):
    """Resuelve el `nvfac_esta` local tras una sincronizacion.

    - Un origen final (estado A/R o ueve 031/033) manda siempre.
    - Un origen intermedio (030/032/vacio) conserva el estado local si ya
      avanzo el flujo propio; si el local esta en analisis, toma el origen.

    current_state: estado local previo (None si es una factura nueva).
    origin_state:  Nvfac_esta que devuelve documenteme.
    origin_ueve:   Nvfac_ueve que devuelve documenteme.
    """
    code = normalize(origin_ueve)
    if code in FINAL_STATE_BY_CODE:
        return FINAL_STATE_BY_CODE[code]
    if origin_state in ("A", "R"):
        return origin_state
    if current_state in advanced_states:
        return current_state
    return origin_state


def resolve_ueve(current_ueve, origin_ueve):
    """Resuelve el `nvfac_ueve` local priorizando el origen.

    Un ueve final local (031/033) nunca baja a un valor intermedio porque
    representa una notificacion propia ya confirmada; cualquier otro caso
    toma el valor de documenteme (incluido vacio).
    """
    if is_final(current_ueve) and not is_final(origin_ueve):
        return normalize(current_ueve)
    return origin_ueve


def start_code(intent, origin_ueve):
    """Primer evento a enviar segun la secuencia y el ueve de origen.

    - Origen final (031/033): None, no hay nada que notificar.
    - Origen 030/032: el siguiente codigo de la secuencia.
    - Vacio o desconocido: el primer codigo (030).

    intent: "A" (aprobacion) o "R" (rechazo).
    """
    from qp_supplier_front.uses_cases.documenteme.event_retry import (
        next_code,
        sequence_for,
    )

    sequence = sequence_for(intent)
    code = normalize(origin_ueve)
    if code in FINAL_CODES:
        return None
    if code in sequence:
        return next_code(intent, code)
    return sequence[0]
