# -*- coding: utf-8 -*-
"""
auto_approve_confirmation.py (documenteme) -- infraestructura
=============================================================
Notificacion asincronica de APROBACION a documenteme (030 -> 032 -> 033).

Replica el patron de auto_reject.py pero para la secuencia de aprobacion
cuyo evento final es 033:

  1. El servicio update_document recibe la confirmacion de BC
     (invoice_id + confirmation_id), guarda el confirmation_id, marca el
     documento en estado "PA" (En proceso de Aprobacion) y encola este job.
  2. El job envía la secuencia 030 -> 032 -> 033 con delay entre eventos y
     reintentos, reanudando un paso antes del ultimo evento con error.
  3. Si la secuencia completa tiene exito, el documento se marca "A"
     (Aprobado) con nvfac_ueve "033" y se resuelven sus alertas.
  4. Si se agotan los intentos, se inserta una alerta y el documento
     permanece en "PA" (En proceso de Aprobacion) para reintentarse.
"""

import time

import frappe

from qp_supplier_front.infrastructure.adapters.documenteme_http_adapter import (
    get_company_tax_id,
    get_event_endpoint,
    raw_http,
)
from qp_supplier_front.resources.documenteme._alerts import (
    insert_alert,
    resolve_open_alerts,
)
from qp_supplier_front.resources.documenteme import simulation
from qp_supplier_front.uses_cases.documenteme.event_notifier import (
    _append_log,
    _is_error,
    _build_payload,
)

APPROVE_JOB_METHOD = (
    "qp_supplier_front.resources.documenteme.auto_approve_confirmation.approve_confirmation_batch_job"
)

APPROVAL_EVENT_ORDER = ["030", "032", "033"]

APPROVAL_EVENT_CONFIG = {
    "030": {"nvint_desc": "Factura aprobada"},
    "032": {"nvint_desc": "Factura aprobada"},
    "033": {"nvfac_esta": "A", "nvint_desc": "Factura aprobada"},
}


def get_approval_config():
    """Reutiliza la configuracion de reintentos del setup global."""
    return {
        "max_attempts": int(frappe.db.get_single_value(
            "qp_SP_MasterSetup", "reject_retry_max_attempts") or 5),
        "retry_interval": int(frappe.db.get_single_value(
            "qp_SP_MasterSetup", "reject_retry_interval_seconds") or 60),
        "event_delay": int(frappe.db.get_single_value(
            "qp_SP_MasterSetup", "reject_event_delay_seconds") or 60),
    }


def enqueue_approve_confirmation(doc_name):
    """Encola el job de fondo que notifica la aprobacion a documenteme."""
    frappe.enqueue(
        APPROVE_JOB_METHOD,
        doc_names=[doc_name],
        queue="long",
        timeout=14400,
        job_name="approve confirmation {}".format(doc_name),
    )


# =========================================================================
# Reanudacion de la secuencia de aprobacion
# =========================================================================
def get_approval_resume_index(event_logs):
    """Indice de APPROVAL_EVENT_ORDER desde donde reanudar el envio.

    Reanuda un paso antes del ultimo evento con error. Misma idea que
    get_reject_resume_index pero para la secuencia de aprobacion (033).
    """
    last_error_index = None
    for log in (event_logs or []):
        if _log_is_error(log):
            event_code = log.get("event_code")
            if event_code in APPROVAL_EVENT_ORDER:
                last_error_index = APPROVAL_EVENT_ORDER.index(event_code)
    if last_error_index is None:
        return 0
    return max(0, last_error_index - 1)


def _log_is_error(log):
    import json

    response = log.get("response")
    status = log.get("status")
    try:
        status = int(status)
    except (TypeError, ValueError):
        status = None
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except (TypeError, ValueError):
            pass
    return _is_error(response, status)


def build_approval_events(doc, company_tax_id, resume_index, base_state=None):
    """Eventos de aprobacion pendientes desde resume_index hasta el final."""
    events = []
    for idx, event_code in enumerate(APPROVAL_EVENT_ORDER):
        if idx < resume_index:
            continue
        events.append({
            "event_code": event_code,
            "payload": _build_payload(
                doc, event_code, APPROVAL_EVENT_CONFIG, company_tax_id,
                base_state=base_state,
            ),
        })
    return events


def is_sequence_successful(sent):
    """True si el ultimo evento enviado es el 033 sin error (aprobacion ok)."""
    last = sent[-1] if sent else None
    if not last or last["event_code"] != "033":
        return False
    return not _is_error(last["response"], last["status"])


# =========================================================================
# Job de fondo
# =========================================================================
def approve_confirmation_batch_job(doc_names):
    if simulation.is_simulation_enabled():
        company_tax_id = simulation.get_company_tax_id()
        url, headers, method = simulation.get_event_endpoint()
    else:
        company_tax_id = get_company_tax_id()
        url, headers, method = get_event_endpoint()
    config = get_approval_config()

    all_results = []
    for doc_name in (doc_names or []):
        doc = frappe.get_doc("qp_SP_DocumentDetail", doc_name)
        result = _approve_one(doc, config, company_tax_id, url, headers, method)
        all_results.append((doc_name, result))

    frappe.db.commit()
    return all_results


def _approve_one(doc, config, company_tax_id, url, headers, method):
    result = {"doc": doc.name, "approved": False, "attempts": 0, "error": None}

    # En la secuencia de aprobacion, los eventos 030/032 notifican con el
    # estado "BCC" (Creada en BC); solo el 033 lleva "A" (Aprobado).
    base_state = "BCC"

    for attempt_no in range(1, config["max_attempts"] + 1):
        result["attempts"] = attempt_no
        if attempt_no > 1:
            time.sleep(config["retry_interval"])

        resume_index = get_approval_resume_index(doc.get("event_logs"))
        events = build_approval_events(
            doc, company_tax_id, resume_index, base_state=base_state
        )

        sent = []
        for event in events:
            response, status = _send_event(
                event["payload"], url, headers, method
            )
            sent.append({
                "event_code": event["event_code"],
                "payload": event["payload"],
                "response": response,
                "status": status,
            })
            _append_log(
                doc,
                event["event_code"],
                event["payload"],
                response,
                status,
                make_now,
            )
            doc.save()
            frappe.db.commit()
            if event["event_code"] != "033":
                time.sleep(config["event_delay"])
            if _is_error(response, status):
                break

        if is_sequence_successful(sent):
            _mark_approved(doc)
            result["approved"] = True
            return result

    insert_alert(
        doc.name,
        "No se ha podido notificar la aprobacion en documenteme. "
        "Se reintentara en la proxima sincronizacion.",
        make_now(),
    )
    result["error"] = "Maximo de intentos alcanzado"
    return result


def _send_event(payload, url, headers, method):
    sender = (
        simulation.http_event
        if simulation.is_simulation_enabled()
        else raw_http
    )
    try:
        return sender(payload, url, headers, method)
    except Exception as error:
        return {"errorInterno": str(error)}, 500


def _mark_approved(doc):
    doc.nvfac_esta = "A"
    doc.qp_is_event_completed = 1
    doc.nvfac_ueve = "033"
    resolve_open_alerts(doc.name)
    doc.save()


def make_now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
