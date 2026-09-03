# -*- coding: utf-8 -*-
"""
event_logs.py (uses_cases - documenteme)
=========================================
Nucleo puro del log de notificaciones a documenteme (qp_SP_EventLog y, por
extension, las filas de la child table event_logs). Sin frappe, sin base:
recibe filas por parametro y retorna decisiones y vistas formateadas.

Objetivo: mantener el log limpio frente a los reintentos.

Regla de escritura (plan_event_log):
  - Primera vez que se envia un codigo -> anexar fila.
  - Re-envio EXITOSO de un codigo cuya ultima fila ya fue exitosa
    (p. ej. el 030/032 que se reenvian al reiniciar la secuencia desde 030
    tras un fallo del 033/031) -> actualizar ESA fila en sitio (fecha nueva)
    sin duplicarla.
  - Intento fallido -> anexar fila nueva (se conserva el historial de los
    fallos, que se muestra en el timeline de notificaciones).

Vistas:
  - notification_summary(logs, sequence, doc_state): una linea por codigo de
    la secuencia con estado Ok / En proceso y la fecha de su ultimo intento.
    Es la base del tooltip del icono de alerta.
  - notification_timeline(logs, sequence, doc_state): todas las filas
    retenidas con estado Ok / fail / En proceso. La fila mas reciente de una
    secuencia en curso se etiqueta "en proceso" (se sigue reintentando); las
    fallas historicas quedan como "fail".
"""

import json

APPROVAL_SEQUENCE = ("030", "032", "033")
REJECT_SEQUENCE = ("030", "032", "031")

STATUS_OK = "ok"
STATUS_FAIL = "fail"
STATUS_IN_PROGRESS = "en_proceso"

STATUS_LABELS = {
    STATUS_OK: "Ok",
    STATUS_FAIL: "Error",
    STATUS_IN_PROGRESS: "En proceso",
}

# Marcadores que indican que el evento YA fue emitido / ya esta aplicado.
# Ajustar si documenteme cambia la redaccion de estos mensajes.
ALREADY_APPLIED_MARKERS = (
    "ya cuenta",
    "ya fue emitido",
    "ya existe",
    "estado exitoso",
    "estado exitosamente",
)


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _row_get(row, field, default=None):
    """Lee un campo de una fila sin importar su tipo (dict o objeto live)."""
    if isinstance(row, dict):
        return row.get(field, default)
    getter = getattr(row, "get", None)
    if callable(getter):
        try:
            return getter(field, default)
        except TypeError:
            return getter(field)
    return getattr(row, field, default)


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

    Un evento que "ya existe y esta en estado exitoso" se considera aplicado
    correctamente: se cuenta como exito (se avanza al siguiente evento).
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


def parse_response(response):
    """Normaliza una respuesta almacenada (string JSON o live dict)."""
    if isinstance(response, str):
        try:
            return json.loads(response)
        except (TypeError, ValueError):
            return response
    return response


def row_is_success(row):
    """True si una fila de event_logs representa un intento exitoso.

    Trabaja con filas live (response dict, status int) y persistidas
    (response string JSON, status string).
    """
    response = parse_response(_row_get(row, "response"))
    status = _to_int(_row_get(row, "status"))
    if is_already_applied(response):
        return True
    if status not in (200, 201):
        return False
    if isinstance(response, dict) and response.get("Result") == 1:
        return False
    return True


def event_is_success(response, status):
    """True si una respuesta HTTP de evento es un exito (incl. ya aplicado)."""
    return row_is_success({"response": response, "status": status})


def plan_event_log(existing_rows, new_is_success):
    """Decide si actualizar la ultima fila del codigo o anexar una nueva.

    existing_rows: filas del MISMO event_code, ordenadas de la mas antigua a
    la mas reciente.

    Retorna "update" (re-envio exitoso sobre una fila ya exitosa) o "append".
    """
    if not existing_rows:
        return "append"
    if new_is_success and row_is_success(existing_rows[-1]):
        return "update"
    return "append"


def filter_by_code(event_logs, event_code):
    return [
        row for row in (event_logs or [])
        if _row_get(row, "event_code") == event_code
    ]


def resolve_sequence(doc_state, event_logs):
    """Secuencia de eventos (aprobacion o rechazo) segun el documento.

    - Si se registro un 031 -> rechazo; si un 033 -> aprobacion.
    - Si no hay eventos: el estado del documento decide (PA/BCC -> aprobacion;
      PR -> rechazo). Por defecto aprobacion (el flujo mas comun).
    """
    for row in (event_logs or []):
        code = _row_get(row, "event_code")
        if code == "031":
            return REJECT_SEQUENCE
        if code == "033":
            return APPROVAL_SEQUENCE
    state = doc_state or ""
    if state == "PR":
        return REJECT_SEQUENCE
    return APPROVAL_SEQUENCE


def _segment_logs(event_logs, sequence):
    """Separa las filas por codigo en orden de secuencia.

    Retorna {"code": [filas asc por order de aparicion]}.
    """
    segments = {}
    for code in sequence:
        segments[code] = filter_by_code(event_logs, code)
    return segments


def notification_summary(event_logs, sequence, doc_state=None):
    """Resumen del log: una linea por codigo de la secuencia con su estado.

    Estado por codigo: "ok" si su ultimo intento fue exitoso; "en_proceso" si
    su ultimo intento fallo (se sigue reintentando mientras el documento este
    en proceso). Los codigos sin filas no se incluyen (no se han alcanzado).
    """
    segments = _segment_logs(event_logs, sequence)
    summary = []
    for code in sequence:
        rows = segments.get(code) or []
        if not rows:
            continue
        latest = rows[-1]
        summary.append({
            "event_code": code,
            "status": STATUS_OK if row_is_success(latest) else STATUS_IN_PROGRESS,
            "date": _row_get(latest, "attempt_date") or "",
        })
    return summary


def notification_timeline(event_logs, sequence, doc_state=None):
    """Timeline legible de notificaciones: una fila por reintento retenido.

    - Exitoso -> "ok".
    - La fila MAS RECIENTE de la secuencia (intento actual) -> "en_proceso"
      si sigue reintentandose (fallo).
    - Fallas anteriores -> "fail".
    Retorna las filas en orden de menor a mayor fecha (chronologico); quien
    consume decide el orden visual.
    """
    rows = [
        row for row in (event_logs or [])
        if _row_get(row, "event_code") in sequence
    ]
    rows = sorted(
        rows,
        key=lambda row: str(_row_get(row, "attempt_date") or ""),
    )
    out = []
    for idx, row in enumerate(rows):
        if row_is_success(row):
            status = STATUS_OK
        elif idx == len(rows) - 1:
            status = STATUS_IN_PROGRESS
        else:
            status = STATUS_FAIL
        out.append({
            "event_code": _row_get(row, "event_code") or "",
            "status": status,
            "date": _row_get(row, "attempt_date") or "",
            "error_message": _row_get(row, "error_message") or "",
        })
    return out


def build_notification_tooltip(summary):
    """Tooltip compacto del icono de alerta a partir del resumen.

    Ej.: "030 Ok - 02/09 14:00\n032 Ok - 02/09 14:01\n033 En proceso - 02/09 14:05"
    """
    if not summary:
        return None
    lines = []
    for item in summary:
        label = STATUS_LABELS.get(item.get("status"), item.get("status") or "")
        date = str(item.get("date") or "")[:16]
        lines.append("{0} {1} - {2}".format(
            item.get("event_code") or "", label, date))
    return "\n".join(lines)