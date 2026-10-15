# -*- coding: utf-8 -*-
"""
event_retry.py (documenteme)
============================
Nucleo puro del envio de eventos documenteme UNO POR VEZ.

Reemplaza el modelo de "un job largo con time.sleep" por una maquina de
estados: cada job envia UN solo evento y deja en el documento cual es el
siguiente (`qp_event_pending_code`) y cuando debe enviarse
(`qp_event_next_at`). Un dispatcher (cron cada minuto) encola los vencidos.

Reglas de la secuencia:
  - Rechazo: 030 -> 032 -> 031   (final 031, estado R)
  - Aprobacion: 030 -> 032 -> 033 (final 033, estado A)
  - Exito -> avanza al siguiente codigo.
  - Fallo -> reinicia desde 030.

Conteo de intentos (`qp_event_attempts`):
  Se incrementa en CADA envio fallido y NUNCA se resetea con un exito
  intermedio; solo queda en 0 al completar la secuencia (que ademas deja el
  documento final). Asi un fallo persistente en 031/033 (precedido de 030/032
  exitosos) igual agota el maximo de intentos.

Sin imports a Frappe: la infraestructura inyecta HTTP/DB/sleep.
"""

from qp_supplier_front.uses_cases.documenteme.event_logs import (
    is_already_applied,
)
from qp_supplier_front.uses_cases.documenteme.event_notifier import _is_error

APPROVAL_SEQUENCE = ("030", "032", "033")
REJECT_SEQUENCE = ("030", "032", "031")

SEQUENCE_BY_INTENT = {
    "A": APPROVAL_SEQUENCE,
    "R": REJECT_SEQUENCE,
}

FINAL_CODE_BY_INTENT = {
    "A": "033",
    "R": "031",
}

FINAL_STATE_BY_INTENT = {
    "A": "A",
    "R": "R",
}

# Estado del documento mientras la secuencia esta en curso (para el dispatcher).
PENDING_STATE_BY_INTENT = {
    "A": "PA",
    "R": "PR",
}


def sequence_for(intent):
    """Secuencia de codigos para el intento dado ('A' o 'R')."""
    return SEQUENCE_BY_INTENT.get(intent) or APPROVAL_SEQUENCE


def first_code(intent):
    """Primer evento de la secuencia (siempre '030')."""
    return sequence_for(intent)[0]


def is_final_code(intent, code):
    """True si el codigo es el evento final de la secuencia."""
    return code == FINAL_CODE_BY_INTENT.get(intent)


def next_code(intent, code):
    """Codigo siguiente al actual, o None si el actual es el final."""
    sequence = sequence_for(intent)
    try:
        idx = sequence.index(code)
    except ValueError:
        return first_code(intent)
    if idx + 1 >= len(sequence):
        return None
    return sequence[idx + 1]


def intent_from_state(state):
    """Intento por defecto segun el estado (para documentos legados).

    PR -> rechazo (R); cualquier otro (PA) -> aprobacion (A).
    """
    return "R" if state == "PR" else "A"


def resolve_intent(doc):
    """Intento del documento: el guardado o, si falta, inferido del estado."""
    intent = doc.get("qp_event_sequence")
    if intent in SEQUENCE_BY_INTENT:
        return intent
    return intent_from_state(doc.get("nvfac_esta"))


def resolve_pending_code(doc, intent):
    """Proximo codigo: el guardado o, si falta/nunca valido, el primero."""
    code = doc.get("qp_event_pending_code")
    if code in sequence_for(intent):
        return code
    return first_code(intent)


def send_was_successful(response, status):
    """True si el envio cuenta como exito (incluye 'ya aplicado')."""
    if is_already_applied(response):
        return True
    return not _is_error(response, status)


def next_attempt_count(current_attempts, was_successful):
    """Intentos fallidos acumulados tras un envio.

    Incrementa ante un fallo; NO se resetea con un exito intermedio (solo la
    finalizacion de la secuencia deja el contador en 0).
    """
    if was_successful:
        return current_attempts or 0
    return (current_attempts or 0) + 1
