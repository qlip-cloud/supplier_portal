# -*- coding: utf-8 -*-
"""
reject_retry.py (documenteme)
=============================
Nucleo puro del reintento del rechazo de facturas documenteme.
No tiene imports a Frappe. La logica de reanudacion y las decisiones de
reintento viven aqui; la infraestructura (HTTP, DB, sleep) se inyecta.

El servidor documenteme es lento en aplicar los eventos: un HTTP 200/201
no garantiza que el cambio ya este aplicado (ej. el 032 tardo mas de 2 min
en reflejarse). Por eso, ante cualquier fallo, el siguiente intento
reinicia la secuencia completa desde el 030 para garantizar que todos los
eventos se vuelvan a emitir en orden.

Reglas de reanudacion (segun el flujo definido):
- cualquier error en 030/032/031 -> siguiente intento reenvia 030, 032, 031
- sin errores previos           -> secuencia completa 030, 032, 031
"""

import json

from qp_supplier_front.uses_cases.documenteme.event_notifier import (
    EVENT_ORDER,
    _build_payload,
    _is_error,
)

REJECT_PENDING_STATES = ("E", "PR")
REJECT_FINAL_STATE = "R"


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# Marcadores que indican que el evento YA fue emitido / ya esta aplicado.
# Ajustar si documenteme cambia la redaccion de estos mensajes.
ALREADY_APPLIED_MARKERS = (
    "ya cuenta",
    "ya fue emitido",
    "ya existe",
    "estado exitoso",
    "estado exitosamente",
)


def _extract_message(response):
    """Extrae el texto del mensaje del response (dict o string)."""
    if isinstance(response, str):
        return response
    if not isinstance(response, dict):
        return str(response)
    return str(
        response.get("Description")
        or response.get("Message")
        or response.get("message")
        or response.get("error")
        or response.get("Error")
        or ""
    )


def is_already_applied(response):
    """True si documenteme responde que el evento ya fue emitido/aplicado.

    En el flujo de rechazo, un evento que "ya existe y esta en estado
    exitoso" se considera aplicado correctamente: se debe AVANZAR al
    siguiente evento y no contar como error (ni retroceder).

    Marcadores directos ("ya fue emitido", "ya existe") indican por si solos
    que el evento ya fue aplicado. El caso compuesto "ya cuenta con ... en
    estado exitoso" exige ademas un indicio de aplicado/exitoso.
    """
    if not isinstance(response, dict) and not isinstance(response, str):
        return False
    message = _extract_message(response)
    text = message.lower()

    direct_markers = ("ya fue emitido", "ya existe")
    if any(m in text for m in direct_markers):
        return True

    ya_markers = ("ya cuenta", "ya tiene")
    applied_markers = ("estado exitoso", "estado exitosamente",
                       "estado existoso", "estado existosamente")
    has_ya = any(m in text for m in ya_markers)
    has_applied = any(m in text for m in applied_markers)
    return has_ya and has_applied


def _log_is_error(log):
    """Detecta error en una fila de event_logs (live o persistida).

    Al leer desde la BD, `response` es un string JSON y `status` un string;
    al trabajar en memoria, `response` es dict y `status` int.
    Un evento que responde "ya aplicado" se considera exitoso, no error.
    """
    response = log.get("response")
    status = _to_int(log.get("status"))
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except (TypeError, ValueError):
            pass
    if is_already_applied(response):
        return False
    return _is_error(response, status)


def get_reject_resume_index(event_logs):
    """Indice de EVENT_ORDER desde donde reanudar el envio del rechazo.

    Ante cualquier fallo se reinicia la secuencia completa desde el 030
    (ver docstring del modulo). El parametro se conserva para mantener la
    firma, pero siempre se devuelve 0.
    """
    return 0


def _compute_resume_from_attempts(attempts):
    """Indice de reanudacion calculado sobre intentos en memoria.

    Ante cualquier fallo se reinicia desde el 030.
    """
    return 0


def build_retry_events(doc, event_config, company_tax_id, resume_index,
                       base_state=None):
    """Eventos pendientes desde resume_index hasta el final de la secuencia.

    Los estados de los payloads se rigen por la regla documenteme
    (DOCUMENTEME_EVENT_STATES): 030/032 -> E, 031 -> R.
    """
    events = []
    for idx, event_code in enumerate(EVENT_ORDER):
        if idx < resume_index:
            continue
        events.append({
            "event_code": event_code,
            "payload": _build_payload(
                doc, event_code, event_config, company_tax_id,
                base_state=base_state,
            ),
        })
    return events


def is_sequence_successful(sent):
    """True si el ultimo evento enviado es el 031 sin error (rechazo ok).

    Un 031 que responde "ya aplicado" tambien se considera rechazado.
    """
    last = sent[-1] if sent else None
    if not last or last["event_code"] != "031":
        return False
    response = last["response"]
    return (not _is_error(response, last["status"])
            or is_already_applied(response))
