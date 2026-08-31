# -*- coding: utf-8 -*-
"""
reject_memory.py (documenteme simulation)
=========================================
Rechazo automatico en memoria: replica el flujo de auto_reject sobre el
MemoryStore con eventos simulados (030/032/031), para que en el modo
simulador el documento termine en "R" sin tocar la DB real.

El composition root (sync_all_whitelist._launch_reject) lo invoca en lugar de
reject_batch_job cuando el facade de datos es in-memory.
"""

import json

APPROVAL = "aprobacion"
REJECT = "rechazo"


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
        "Nvint_desc": "Rechazo por error de factura",
    }


def _append_event(store, doc_name, event_code, payload, response, status):
    store.insert("qp_SP_EventLog", {
        "parent": doc_name,
        "event_code": event_code,
        "payload": json.dumps(payload),
        "response": json.dumps(response) if not isinstance(response, str) else response,
        "status": status,
    })


def _alert(store, doc_name, message):
    from datetime import datetime
    store.insert("qp_SP_Alert", {
        "parent": doc_name,
        "message": message,
        "creation": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


def _resolve_alerts(store, doc_name):
    for alert in store.query("qp_SP_Alert", filters={"parent": doc_name}):
        store.set_value("qp_SP_Alert", alert["name"], "resolved", 1)


def run_reject(store, doc_names=None):
    """Rechaza automaticamente las facturas simuladas sin OC (regla no_po).

    - Contado: R directo (sin eventos).
    - Credito: PR -> secuencia 030/032/031 -> R (nvfac_ueve 031).

    Retorna {"rejected": [...], "pending": [...]}.
    """
    from qp_supplier_front.resources.documenteme import runtime
    from qp_supplier_front.simulation import references_memory

    components = runtime.resolve()
    event_http_fn = components["event_http_fn"]
    url, headers, method = components["event_endpoint_fn"]()
    company_tax_id = components["company_tax_id_fn"]()

    rejected = []
    pending = []

    for name in (doc_names or []):
        doc = store.get("qp_SP_DocumentDetail", name) or {}
        if not doc or doc.get("nvfac_ueve"):
            continue
        if str(doc.get("nvfac_esta")) not in ("E", "PR"):
            continue

        is_cash = str(doc.get("nvfac_conv")) == "1"
        if is_cash:
            store.set_value("qp_SP_DocumentDetail", name, "nvfac_esta", "R")
            store.set_value("qp_SP_DocumentDetail", name,
                            "qp_is_event_completed", 1)
            _resolve_alerts(store, name)
            rejected.append(doc.get("nvfac_nume"))
            continue

        po = doc.get("nvfac_orde")
        if po and references_memory.memory_po_exists(store, po):
            continue

        store.set_value("qp_SP_DocumentDetail", name, "nvfac_esta", "PR")
        ok = _send_sequence(store, name, company_tax_id,
                            event_http_fn, url, headers, method)
        if ok:
            store.set_value("qp_SP_DocumentDetail", name, "nvfac_esta", "R")
            store.set_value("qp_SP_DocumentDetail", name,
                            "qp_is_event_completed", 1)
            store.set_value("qp_SP_DocumentDetail", name, "nvfac_ueve", "031")
            _resolve_alerts(store, name)
            rejected.append(doc.get("nvfac_nume"))
        else:
            _alert(store, name,
                   "No se ha podido rechazar en documenteme. Se reintentara.")
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