# -*- coding: utf-8 -*-
"""
event_job.py (documenteme) -- infraestructura
=============================================
Envia UN solo evento documenteme por job y programa el siguiente.

Reemplaza a reject_batch_job / approve_confirmation_batch_job (que hacian la
secuencia completa con time.sleep dentro del worker, reteniendolo hasta 4h).
Aqui cada job hace un unico HTTP y termina; el disparo del proximo evento
queda persistido en el documento (qp_event_pending_code / qp_event_next_at) y
lo materializa el dispatcher (event_dispatch.dispatch_pending_events).

Secuencias (uses_cases/documenteme/event_retry):
  - Rechazo:    030 -> 032 -> 031 (final 031, estado R)
  - Aprobacion: 030 -> 032 -> 033 (final 033, estado A)
Exito -> avanza; fallo -> reinicia desde 030.
"""

from datetime import datetime, timedelta

import frappe

from qp_supplier_front.resources.documenteme._alerts import (
    insert_alert,
    resolve_open_alerts,
)
from qp_supplier_front.resources.documenteme import runtime
from qp_supplier_front.services import sync_lock
from qp_supplier_front.uses_cases.documenteme.event_notifier import (
    _append_log,
    _build_payload,
)
from qp_supplier_front.uses_cases.documenteme.event_retry import (
    FINAL_STATE_BY_INTENT,
    first_code,
    is_final_code,
    next_attempt_count,
    next_code,
    resolve_intent,
    resolve_pending_code,
    send_was_successful,
)

EVENT_JOB_METHOD = (
    "qp_supplier_front.resources.documenteme.event_job.run_documenteme_event"
)

EVENT_LOCK_PREFIX = "documenteme_event"
EVENT_LOCK_TTL = 300

# Al agotar los intentos el documento se "aparca" este tiempo antes de
# reintentar con un presupuesto nuevo (evita reenviar/alertar cada minuto).
GIVEUP_BACKOFF_SECONDS = 3600

REJECT_EVENT_CONFIG = {"031": {"nvfac_esta": "R"}}

APPROVAL_EVENT_CONFIG = {
    "030": {"nvint_desc": "Factura aprobada"},
    "032": {"nvint_desc": "Factura aprobada"},
    "033": {"nvfac_esta": "A", "nvint_desc": "Factura aprobada"},
}


def event_lock_domain(doc_name):
    return "{}:{}".format(EVENT_LOCK_PREFIX, doc_name)


def initialize_event_schedule(doc, intent):
    """Deja el documento listo para iniciar la secuencia de eventos."""
    doc.qp_event_sequence = intent
    doc.qp_event_pending_code = first_code(intent)
    doc.qp_event_next_at = _now_str()
    doc.qp_event_attempts = 0


def initialize_event_schedule_db(doc_name, intent):
    """Igual que initialize_event_schedule pero sin disparar hooks (set_value).

    Se usa cuando el estado ya se persistio aparte (p. ej. la confirmacion
    marca PA via set_value) y no se quiere un save extra del documento.
    """
    frappe.db.set_value(
        "qp_SP_DocumentDetail",
        doc_name,
        {
            "qp_event_sequence": intent,
            "qp_event_pending_code": first_code(intent),
            "qp_event_next_at": _now_str(),
            "qp_event_attempts": 0,
        },
    )


def _event_config(intent):
    return APPROVAL_EVENT_CONFIG if intent == "A" else REJECT_EVENT_CONFIG


def _base_state(doc, intent):
    if intent == "A":
        return "BCC"
    return doc.get("qp_reject_orig_state") or "E"


def _now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _future_str(seconds):
    return (datetime.now() + timedelta(seconds=int(seconds or 0))).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _is_due(doc):
    """True si el evento esta vencido (protege contra encolados duplicados)."""
    next_at = doc.get("qp_event_next_at")
    if not next_at:
        return True
    return str(next_at)[:19] <= _now_str()


def schedule_event(doc_name, http_fn=None, lock_token=None, enqueue_fn=None,
                   enqueue=True):
    """Programa el envio de UN evento para el documento.

    - http_fn: si se entrega, ejecuta inline (tests / modo sin worker).
    - enqueue=False: ejecuta inline aunque no se entregue http_fn.
    - si no, encola el job de un evento.
    """
    if http_fn is not None:
        return run_documenteme_event(
            doc_name, http_fn=http_fn, lock_token=lock_token
        )
    if not enqueue:
        return run_documenteme_event(doc_name, lock_token=lock_token)
    kwargs = {"doc_name": doc_name}
    if lock_token:
        kwargs["lock_token"] = lock_token
    if enqueue_fn is not None:
        return enqueue_fn(EVENT_JOB_METHOD, queue="long", timeout=600,
                          job_name="documenteme event {}".format(doc_name),
                          **kwargs)
    return frappe.enqueue(
        EVENT_JOB_METHOD,
        queue="long",
        timeout=600,
        job_name="documenteme event {}".format(doc_name),
        **kwargs
    )


def run_documenteme_event(doc_name, http_fn=None, lock_token=None):
    """Envia UN evento y deja programado el siguiente. Libera el worker.

    lock_token: token del lock ya tomado por el dispatcher (evita re-encolar
    mientras corre). Si no se entrega, el job toma su propio lock.
    """
    from qp_supplier_front.resources.documenteme.auto_reject import (
        get_reject_config,
    )

    components = runtime.resolve()
    if http_fn is None:
        http_fn = components["event_http_fn"]

    domain = event_lock_domain(doc_name)
    if lock_token is not None:
        token = {"token": lock_token}
    else:
        token = sync_lock.acquire(domain, ttl=EVENT_LOCK_TTL)
        if token is None:
            return {"doc": doc_name, "skipped": True,
                    "reason": "En proceso por otro job"}

    try:
        doc = frappe.get_doc("qp_SP_DocumentDetail", doc_name)
        intent = resolve_intent(doc)

        # Idempotencia: si el evento aun no esta vencido (otro job/dispatch ya
        # lo reprogramo), no se reenvia.
        if not _is_due(doc):
            return {"doc": doc_name, "skipped": True, "reason": "not_due"}

        # Kill-switch por factura (solo rechazo): no se envia nada.
        if intent == "R" and not getattr(doc, "qp_reject_retry_enabled", True):
            return {"doc": doc_name, "skipped": True,
                    "reason": "Reintentos deshabilitados"}

        config = get_reject_config()
        company_tax_id = components["company_tax_id_fn"]()
        url, headers, method = components["event_endpoint_fn"]()

        code = resolve_pending_code(doc, intent)
        payload = _build_payload(
            doc,
            code,
            _event_config(intent),
            company_tax_id,
            base_state=_base_state(doc, intent),
        )
        response, status = _send(http_fn, payload, url, headers, method)
        _append_log(doc, code, payload, response, status, _now_str)

        return _apply_outcome(doc, intent, code, response, status, config)
    finally:
        sync_lock.release(domain, token.get("token"))


def _send(http_fn, payload, url, headers, method):
    try:
        response, status = http_fn(payload, url, headers, method)
        return response, status
    except Exception as error:
        return {"errorInterno": str(error)}, 500


def _apply_outcome(doc, intent, code, response, status, config):
    """Actualiza el estado del documento tras UN envio y programa el siguiente."""
    success = send_was_successful(response, status)
    attempts = next_attempt_count(
        int(getattr(doc, "qp_event_attempts", 0) or 0), success
    )
    doc.qp_event_sequence = intent
    doc.qp_event_attempts = attempts

    if success and is_final_code(intent, code):
        doc.nvfac_esta = FINAL_STATE_BY_INTENT[intent]
        doc.qp_is_event_completed = 1
        doc.nvfac_ueve = code
        doc.qp_event_pending_code = ""
        doc.qp_event_next_at = None
        doc.qp_event_attempts = 0
        resolve_open_alerts(doc.name)
        doc.save()
        frappe.db.commit()
        return {"doc": doc.name, "intent": intent, "sent": code, "done": True,
                "state": doc.nvfac_esta, "attempts": 0}

    if not success and attempts >= int(config.get("max_attempts") or 0):
        # Se aparca el documento (presupuesto nuevo tras el backoff) para no
        # reenviar ni alertar en cada tick del dispatcher.
        doc.qp_event_pending_code = ""
        doc.qp_event_next_at = _future_str(GIVEUP_BACKOFF_SECONDS)
        doc.qp_event_attempts = 0
        doc.save()
        insert_alert(
            doc.name,
            "No se ha podido notificar la factura en documenteme. Se "
            "reintentara mas tarde.",
            _now_str(),
            alert_type="ErrorUrgente",
        )
        frappe.db.commit()
        return {"doc": doc.name, "intent": intent, "sent": code, "done": False,
                "error": "Maximo de intentos alcanzado", "attempts": attempts}

    upcoming = next_code(intent, code) if success else first_code(intent)
    delay = config.get("event_delay") if success else config.get("retry_interval")
    doc.qp_event_pending_code = upcoming
    doc.qp_event_next_at = _future_str(delay)
    doc.save()
    frappe.db.commit()
    return {"doc": doc.name, "intent": intent, "sent": code, "done": False,
            "next": upcoming, "attempts": attempts}
