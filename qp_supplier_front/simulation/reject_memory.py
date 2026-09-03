# -*- coding: utf-8 -*-
"""
reject_memory.py (documenteme simulation)
=========================================
Rechazo automatico en memoria: replica el flujo de auto_reject sobre el
MemoryStore con la regla activa (supplier o default del MasterSetup) y
eventos simulados (030/032/031), para que en el modo simulador el documento
termine en "R" sin tocar la DB real.

Reglas:
- Contado (nvfac_conv 1): NUNCA se auto-rechaza por la regla (gate de
  aprobacion/asignacion); se omite.
- Credito: se rechaza si la regla activa lo exige (should_auto_reject) y la
  secuencia de eventos tiene exito.
- Sin regla activa (None / no_action): no se rechaza nadie.

El composition root (sync_all_whitelist._launch_reject) lo invoca en lugar de
reject_batch_job cuando el facade de datos es in-memory.
"""

import json

from qp_supplier_front.uses_cases.documenteme.conversion import is_cash_invoice


def _memory_timeline(store):
    from qp_supplier_front.simulation.timeline_memory import MemoryTimelineAdapter
    return MemoryTimelineAdapter(store)


def _payload(doc, event_code, company_tax_id):
    from qp_supplier_front.uses_cases.documenteme.event_notifier import (
        DOCUMENTEME_EVENT_STATES,
    )

    return {
        "Nvemp_nnit": company_tax_id,
        "Nvpro_ndoc": doc.get("nvpro_ndoc"),
        "Nvfac_cont": doc.get("nvfac_cont"),
        "Nvfac_esta": DOCUMENTEME_EVENT_STATES.get(event_code, "E"),
        "Nveve_dian": event_code,
        "Nvint_desc": doc.get("qp_motive") or "Rechazo por error de factura",
    }


def _append_event(store, doc_name, event_code, payload, response, status):
    from datetime import datetime

    from qp_supplier_front.uses_cases.documenteme.event_logs import (
        event_is_success,
        plan_event_log,
    )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    serialized = (
        json.dumps(response) if not isinstance(response, str) else response
    )
    existing = store.query(
        "qp_SP_EventLog",
        filters={"parent": doc_name, "event_code": event_code},
    )
    if plan_event_log(existing, event_is_success(response, status)) == "update":
        store.update("qp_SP_EventLog", existing[-1]["name"], {
            "status": status,
            "response": serialized,
            "error_message": "",
            "attempt_date": now,
        })
        return
    store.insert("qp_SP_EventLog", {
        "parent": doc_name,
        "event_code": event_code,
        "payload": json.dumps(payload),
        "response": serialized,
        "status": status,
        "error_message": "",
        "attempt_date": now,
    })


def _alert(store, doc_name, message, alert_type="Alerta"):
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    store.insert("qp_SP_Alert", {
        "parent": doc_name,
        "alert_message": message,
        "alert_type": alert_type,
        "status": "Abierta",
        "alert_date": now,
        "creation": now,
    })


def _resolve_alerts(store, doc_name):
    for alert in store.query("qp_SP_Alert", filters={"parent": doc_name}):
        store.set_value("qp_SP_Alert", alert["name"], "status", "Resuelta")


def _receipt_for_po(store):
    """Callback escalar (total o None) de recibos por OC para has_receipt_match."""
    from qp_supplier_front.simulation import references_memory

    def fn(purchase_order):
        return references_memory.memory_receipts_total(store, purchase_order)
    return fn


def run_reject(store, doc_names=None):
    """Rechaza automaticamente las facturas simuladas segun la regla activa.

    - Contado: nunca se rechaza (se omite; va a aprobacion/asignacion).
    - Credito: PR -> 030/032/031 -> R solo si la regla activa lo exige.
    - Sin regla activa: no se rechaza nada.

    Retorna {"rejected": [...], "pending": [...]}.
    """
    from qp_supplier_front.resources.documenteme import runtime
    from qp_supplier_front.simulation import references_memory
    from qp_supplier_front.uses_cases.documenteme.auto_reject import (
        get_reject_motive,
        has_po_match,
        has_receipt_match,
        is_active_rule,
        should_auto_reject,
    )

    components = runtime.resolve()
    event_http_fn = components["event_http_fn"]
    url, headers, method = components["event_endpoint_fn"]()
    company_tax_id = components["company_tax_id_fn"]()

    rejected = []
    pending = []

    # Seleccion manual en curso (recibos reclamados): se excluye del rechazo
    # automatico (manual excluye auto).
    claimed = references_memory.memory_claimed_invoice_numbers(store)

    for name in (doc_names or []):
        doc = store.get("qp_SP_DocumentDetail", name) or {}
        if not doc or doc.get("nvfac_ueve"):
            continue
        if doc.get("nvfac_nume") in claimed:
            continue
        if str(doc.get("nvfac_esta")) not in ("E", "PR"):
            continue
        if is_cash_invoice(str(doc.get("nvfac_conv"))):
            continue

        rule = references_memory.memory_resolve_rule(store, doc)
        if not is_active_rule(rule):
            continue

        po_match = has_po_match(
            doc, lambda po: references_memory.memory_po_exists(store, po))
        receipt_match = has_receipt_match(doc, _receipt_for_po(store))

        if not should_auto_reject(po_match, receipt_match,
                                  rule.get("rule_code")):
            continue

        store.set_value("qp_SP_DocumentDetail", name, "qp_motive",
                        get_reject_motive(rule))
        old_state = store.get_value("qp_SP_DocumentDetail", name, "nvfac_esta")
        store.set_value("qp_SP_DocumentDetail", name, "nvfac_esta", "PR")
        _memory_timeline(store).set_state(name, "PR", old_state=old_state)
        ok = _send_sequence(store, name, company_tax_id,
                            event_http_fn, url, headers, method)
        if ok:
            old_state = store.get_value("qp_SP_DocumentDetail", name, "nvfac_esta")
            store.set_value("qp_SP_DocumentDetail", name, "nvfac_esta", "R")
            store.set_value("qp_SP_DocumentDetail", name,
                            "qp_is_event_completed", 1)
            store.set_value("qp_SP_DocumentDetail", name, "nvfac_ueve", "031")
            _memory_timeline(store).set_state(
                name, "R",
                extra_fields={"qp_is_event_completed": 1},
                old_state=old_state,
            )
            _resolve_alerts(store, name)
            rejected.append(doc.get("nvfac_nume"))
        else:
            _alert(store, name,
                   "No se ha podido rechazar en documenteme. Se reintentara.",
                   alert_type="ErrorUrgente")
            pending.append(doc.get("nvfac_nume"))

    return {"rejected": rejected, "pending": pending}


def _send_sequence(store, doc_name, company_tax_id,
                   event_http_fn, url, headers, method):
    from qp_supplier_front.uses_cases.documenteme.event_notifier import (
        _is_error,
    )

    doc = store.get("qp_SP_DocumentDetail", doc_name) or {}
    for event_code in ("030", "032", "031"):
        payload = _payload(doc, event_code, company_tax_id)
        try:
            response, status = event_http_fn(payload, url, headers, method)
        except Exception:
            response, status = {"errorInterno": "reject sim"}, 500
        _append_event(store, doc_name, event_code, payload, response, status)
        if _is_error(response, status):
            return False
    return True