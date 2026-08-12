"""
auto_reject.py (documenteme) — infraestructura
==============================================
Cablea el nucleo puro de rechazo automatico (uses_cases/documenteme/auto_reject)
con implementaciones Frappe y orquesta la notificacion a documenteme.

El flujo replica exactamente el rechazo manual (reject_document):
1. run_auto_reject() escanea facturas en estado "E", resuelve la regla por
   proveedor (con fallback al setup global) y recolecta los candidatos.
2. Los candidatos se encolan como job de fondo (reject_batch_job) para no
   atorar el servicio. Dentro del job cada documento envia la secuencia
   completa 030 -> 032 -> 031 (misma logica que send_event_sequence, con
   resume por event_logs y detencion ante el primer error). Los workers solo
   hacen HTTP puro (sin acceso a frappe/db) y la persistencia se hace en el
   hilo principal.
3. La factura se marca "R" (con qp_motive, qp_auto_reject_rule, nvfac_ueve y
   qp_is_event_completed) solo cuando la secuencia completa tiene exito.
   Si falla, queda en "E" y el siguiente ciclo la vuelve a evaluar.
"""

import json

import frappe
import requests
from concurrent.futures import ThreadPoolExecutor

from qp_authorization.use_case.basic.authorize import (
    get_enviroment,
    get_headers,
)
from qp_supplier_front.constant.endpoint import DOCUMENTEME_EVENT_DOCUMENT
from qp_supplier_front.resources.documenteme.auto_assign import get_receipt_total
from qp_supplier_front.uses_cases.documenteme.auto_reject import (
    auto_reject as auto_reject_core,
    resolve_auto_reject_config,
)
from qp_supplier_front.uses_cases.documenteme.event_notifier import (
    EVENT_ORDER,
    _append_log,
    _build_payload,
    _get_last_event_idx,
    _is_error,
)

MAX_HTTP_WORKERS = 5
REJECT_JOB_METHOD = "qp_supplier_front.resources.documenteme.auto_reject.reject_batch_job"


def run_auto_reject(http_fn=None):
    rejects = auto_reject_core(
        candidates_fn=get_candidates,
        resolve_rule_fn=resolve_rule,
        po_exists_fn=po_exists,
        receipt_for_po_fn=receipt_for_po,
    )
    frappe.db.commit()

    if rejects:
        if http_fn is not None:
            reject_batch_job(rejects, http_fn=http_fn)
        else:
            frappe.enqueue(
                REJECT_JOB_METHOD,
                rejects=rejects,
                queue="long",
                timeout=14400,
                job_name="auto reject documents",
            )

    return {"rejected": [reject["doc"] for reject in rejects]}


@frappe.whitelist()
def auto_reject():
    try:
        result = run_auto_reject()
        frappe.db.commit()
        return {"success": True, "data": result, "msg": "Rechazo automatico ejecutado"}
    except Exception as error:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "auto_reject")
        return {"success": False, "error": str(error)}


# =========================================================================
# Callbacks de infraestructura (scan)
# =========================================================================
def get_candidates():
    return frappe.get_all(
        "qp_SP_DocumentDetail",
        filters={
            "nvfac_ueve": ["is", "not set"],
            "nvfac_esta": "E",
        },
        fields=[
            "name",
            "nvfac_nume",
            "nvpro_ndoc",
            "nvfac_orde",
            "nvfac_esta",
            "nvfac_ueve",
            "nvfac_cont",
        ],
    )


def resolve_rule(doc):
    supplier_rule = get_supplier_rule(doc.get("nvpro_ndoc"))
    setup_rule = get_setup_default_rule()
    return resolve_auto_reject_config(supplier_rule, setup_rule)


def get_supplier_rule(tax_id):
    if not tax_id:
        return None
    suppliers = frappe.get_all(
        "Supplier",
        filters={"tax_id": tax_id},
        pluck="name",
        limit=1,
    )
    if not suppliers:
        return None
    rule_name = frappe.db.get_value("Supplier", suppliers[0], "auto_reject")
    return get_rule(rule_name)


def get_setup_default_rule():
    rule_name = frappe.db.get_single_value("qp_SP_MasterSetup", "auto_reject")
    return get_rule(rule_name)


def get_rule(rule_name):
    if not rule_name:
        return None
    if not frappe.db.exists("qp_SP_AutoRejectRule", rule_name):
        return None
    values = frappe.db.get_value(
        "qp_SP_AutoRejectRule",
        rule_name,
        ["rule_name", "rule_code", "enabled", "motive"],
    )
    if not values:
        return None
    return {
        "rule_name": values[0],
        "rule_code": values[1],
        "enabled": values[2],
        "motive": values[3],
    }


def po_exists(purchase_order_number):
    if not purchase_order_number:
        return False
    return bool(frappe.db.exists("Purchase Order", purchase_order_number))


def receipt_for_po(purchase_order_number):
    return get_receipt_total(purchase_order_number)


# =========================================================================
# Rechazo (job de fondo con HTTP paralelo) — replica de reject_document
# =========================================================================
def reject_batch_job(rejects, http_fn=None):
    docs_by_name = {}
    doc_tasks = []
    company_tax_id = get_company_tax_id()

    for item in (rejects or []):
        doc_name = item["doc"]
        doc = frappe.get_doc("qp_SP_DocumentDetail", doc_name)
        if doc.nvfac_esta != "E":
            continue

        docs_by_name[doc_name] = {
            "doc": doc,
            "motive": item["motive"],
            "rule": item["rule"],
        }
        event_config = {"031": {"nvfac_esta": "R"}}
        last_idx = _get_last_event_idx(doc.get("event_logs"))
        events = []
        for idx, event_code in enumerate(EVENT_ORDER):
            if idx <= last_idx:
                continue
            events.append({
                "event_code": event_code,
                "payload": _build_payload(doc, event_code, event_config, company_tax_id),
            })
        if events:
            doc_tasks.append({"doc_name": doc_name, "events": events})

    results = dispatch_http(doc_tasks, http_fn=http_fn)
    apply_batch_results(docs_by_name, results)
    frappe.db.commit()


def dispatch_http(doc_tasks, http_fn=None):
    if not doc_tasks:
        return []
    url, headers, method = get_event_endpoint()
    sender = http_fn if http_fn is not None else raw_http

    def raw(task):
        sent = []
        for event in task["events"]:
            response, status = sender(event["payload"], url, headers, method)
            sent.append({
                "event_code": event["event_code"],
                "payload": event["payload"],
                "response": response,
                "status": status,
            })
            if _is_error(response, status):
                break
        return task["doc_name"], sent

    with ThreadPoolExecutor(max_workers=MAX_HTTP_WORKERS) as pool:
        return list(pool.map(raw, doc_tasks))


def get_event_endpoint():
    enviroment, endpoint, _ = get_enviroment(DOCUMENTEME_EVENT_DOCUMENT)
    url = enviroment.get_url(endpoint.url)
    return url, get_headers(enviroment), endpoint.method


def raw_http(payload, url, headers, method):
    data = json.dumps(payload)
    try:
        resp = requests.request(method, url, headers=headers, data=data)
        return json.loads(resp.text), resp.status_code
    except Exception as error:
        return {"errorInterno": str(error)}, 500


def apply_batch_results(docs_by_name, results):
    for doc_name, sent in results:
        meta = docs_by_name[doc_name]
        doc = meta["doc"]

        for attempt in sent:
            _append_log(
                doc,
                attempt["event_code"],
                attempt["payload"],
                attempt["response"],
                attempt["status"],
                make_now,
            )

        sequence_ok = (
            bool(sent)
            and sent[-1]["event_code"] == "031"
            and not _is_error(sent[-1]["response"], sent[-1]["status"])
        )
        if sequence_ok:
            doc.nvfac_esta = "R"
            doc.qp_motive = meta["motive"]
            doc.qp_is_event_completed = 1
            doc.nvfac_ueve = "031"
            doc.qp_auto_reject_rule = meta["rule"]
        doc.save()


# =========================================================================
# Helpers
# =========================================================================
def get_company_tax_id():
    company = frappe.get_doc("Company", frappe.defaults.get_user_default("company"))
    return company.tax_id


def make_now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
