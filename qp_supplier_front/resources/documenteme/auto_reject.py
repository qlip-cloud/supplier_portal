"""
auto_reject.py (documenteme) — infraestructura
==============================================
Cablea el nucleo puro de rechazo automatico (uses_cases/documenteme/auto_reject)
con implementaciones Frappe y orquesta la notificacion a documenteme.

El rechazo es ASINCRONO y usa un estado intermedio "En proceso" (P):

1. run_auto_reject() escanea facturas pendientes, tanto nuevas en estado "E"
   (resuelve la regla por proveedor con fallback al setup global) como las
   que ya quedaron "en proceso" (P) por un rechazo manual o previo fallido.
2. Cada factura pasa a estado "PR" (En proceso de rechazo) de inmediato, de
   forma que queda visible en la UI y no se vuelve a evaluar precio/regla.
3. Se encola un job de fondo (reject_batch_job) que intenta la secuencia
   030 -> 032 -> 031 con:
   - delay configurable ENTRE eventos de la misma secuencia
     (reject_event_delay_seconds) porque el servidor externo tarda en
     aplicar cada cambio.
   - reintentos (hasta reject_retry_max_attempts, por defecto 5) separados
     por reject_retry_interval_seconds.
   - ante cualquier fallo, cada intento reinicia la secuencia completa
     desde 030 (ver reject_retry.get_reject_resume_index).
4. Si la secuencia completa tiene exito, la factura se marca "R" y se
   resuelven sus alertas. Si se agotan los intentos, se inserta una alerta
   de "no se ha podido rechazar" y la factura permanece en "PR" para
   reintentarse en el siguiente ciclo (mientras qp_reject_retry_enabled=1).
5. Kill-switch POR FACTURA: si qp_reject_retry_enabled=0, ese documento no
   envia peticiones aunque este en "PR".
"""

import time

import frappe
import requests
from concurrent.futures import ThreadPoolExecutor

from qp_supplier_front.infrastructure.adapters.documenteme_http_adapter import (
    get_company_tax_id as _adapter_get_company_tax_id,
    get_event_endpoint,
    get_receipt_total,
    raw_http as _adapter_raw_http,
)
from qp_supplier_front.resources.documenteme._alerts import (
    insert_alert,
    resolve_open_alerts,
)
from qp_supplier_front.resources.documenteme import simulation
from qp_supplier_front.uses_cases.documenteme.auto_reject import (
    auto_reject as auto_reject_core,
    resolve_auto_reject_config,
)
from qp_supplier_front.uses_cases.documenteme.event_notifier import (
    _append_log,
    _is_error,
)
from qp_supplier_front.uses_cases.documenteme.reject_retry import (
    REJECT_PENDING_STATES,
    build_retry_events,
    get_reject_resume_index,
    is_already_applied,
    is_sequence_successful,
)

MAX_HTTP_WORKERS = 5
REJECT_JOB_METHOD = "qp_supplier_front.resources.documenteme.auto_reject.reject_batch_job"

EVENT_CONFIG = {"031": {"nvfac_esta": "R"}}


def get_reject_config():
    """Configuracion global de reintentos desde qp_SP_MasterSetup."""
    return {
        "max_attempts": int(frappe.db.get_single_value(
            "qp_SP_MasterSetup", "reject_retry_max_attempts") or 5),
        "retry_interval": int(frappe.db.get_single_value(
            "qp_SP_MasterSetup", "reject_retry_interval_seconds") or 60),
        "event_delay": int(frappe.db.get_single_value(
            "qp_SP_MasterSetup", "reject_event_delay_seconds") or 60),
    }


def run_auto_reject(http_fn=None, enqueue=True, doc_names=None):
    rejects = auto_reject_core(
        candidates_fn=get_candidates,
        resolve_rule_fn=resolve_rule,
        po_exists_fn=po_exists,
        receipt_for_po_fn=receipt_for_po,
        doc_names=doc_names,
    )

    # Guard / kill-switch: los docs con retry deshabilitado no se envian.
    rejects = [r for r in rejects if _retry_enabled_for(r["doc"])]
    _mark_pending(rejects)
    frappe.db.commit()

    if rejects and enqueue and http_fn is None:
        frappe.enqueue(
            REJECT_JOB_METHOD,
            rejects=rejects,
            queue="long",
            timeout=14400,
            job_name="auto reject documents",
        )
    elif rejects:
        reject_batch_job(rejects, http_fn=http_fn)

    return {"rejected": [reject["doc"] for reject in rejects]}


def _retry_enabled_for(doc_ident):
    """Consulta qp_reject_retry_enabled por nombre de documento.

    Los items del scan traen el nombre del documento en la clave "doc".
    """
    value = frappe.db.get_value(
        "qp_SP_DocumentDetail", doc_ident, "qp_reject_retry_enabled"
    )
    return bool(value)


def _mark_pending(rejects):
    """Marca como "PR" (En proceso de rechazo) las facturas nuevas (estado E).

    Si una factura ya esta en "PR" (reintento), conserva sus datos de rechazo.
    Se persistira el motivo/regla de la factura: para las nuevas se calculan
    desde la regla; la infraestructura lee estos campos en el job.
    """
    for item in (rejects or []):
        doc_name = item["doc"]
        doc = frappe.get_doc("qp_SP_DocumentDetail", doc_name)
        if doc.nvfac_esta != "E":
            continue
        doc.nvfac_esta = "PR"
        if not doc.qp_reject_orig_state:
            doc.qp_reject_orig_state = "E"
        if item.get("motive"):
            doc.qp_motive = item["motive"]
        if item.get("rule"):
            doc.qp_auto_reject_rule = item["rule"]
        doc.save()


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


@frappe.whitelist()
def toggle_reject_retry(doc_name):
    """Kill-switch por factura: habilita/deshabilita los reintentos de rechazo."""
    try:
        doc = frappe.get_doc("qp_SP_DocumentDetail", doc_name)
        doc.qp_reject_retry_enabled = 0 if doc.qp_reject_retry_enabled else 1
        doc.save()
        frappe.db.commit()
        return {"success": True, "enabled": bool(doc.qp_reject_retry_enabled)}
    except Exception as error:
        frappe.db.rollback()
        return {"success": False, "error": str(error)}


# =========================================================================
# Callbacks de infraestructura (scan)
# =========================================================================
def get_candidates(doc_names=None):
    filters = {
        "nvfac_ueve": ["is", "not set"],
        "nvfac_esta": ["in", list(REJECT_PENDING_STATES)],
    }
    if doc_names:
        filters["name"] = ["in", list(doc_names)]

    return frappe.get_all(
        "qp_SP_DocumentDetail",
        filters=filters,
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
# Rechazo (job de fondo con reintentos)
# =========================================================================
def reject_batch_job(rejects, http_fn=None):
    if http_fn is None:
        http_fn = (
            simulation.http_event
            if simulation.is_simulation_enabled()
            else None
        )
    config = get_reject_config()
    if simulation.is_simulation_enabled():
        company_tax_id = simulation.get_company_tax_id()
        url, headers, method = simulation.get_event_endpoint()
    else:
        company_tax_id = get_company_tax_id()
        url, headers, method = get_event_endpoint()
    sender = http_fn if http_fn is not None else raw_http

    all_results = []
    for item in (rejects or []):
        doc_name = item["doc"]
        doc = frappe.get_doc("qp_SP_DocumentDetail", doc_name)
        result = _reject_one(
            doc,
            config,
            company_tax_id,
            url,
            headers,
            method,
            sender,
        )
        all_results.append((doc_name, result))

    frappe.db.commit()
    return all_results


def _reject_one(doc, config, company_tax_id, url, headers, method, sender):
    """Reintenta la secuencia para un documento hasta agotar intentos.

    Retorna un dict con el estado final del intento para permitir tests.
    """
    result = {"doc": doc.name, "rejected": False, "attempts": 0, "error": None}

    # Kill-switch por factura: no se envia nada.
    if not getattr(doc, "qp_reject_retry_enabled", True):
        result["error"] = "Reintentos deshabilitados"
        return result

    base_state = getattr(doc, "qp_reject_orig_state", None) or "E"

    for attempt_no in range(1, config["max_attempts"] + 1):
        result["attempts"] = attempt_no
        if attempt_no > 1:
            time.sleep(config["retry_interval"])

        resume_index = get_reject_resume_index(doc.get("event_logs"))
        events = build_retry_events(
            doc,
            EVENT_CONFIG,
            company_tax_id,
            resume_index,
            base_state=base_state,
        )
        if not events:
            sent = []
        else:
            sent = []
            for event in events:
                response, status = _send_event(
                    event, url, headers, method, sender
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
                # Espera entre eventos (no tras el ultimo).
                if event["event_code"] != "031":
                    time.sleep(config["event_delay"])
                # Un evento que "ya esta aplicado" cuenta como exito: se
                # avanza al siguiente (p. ej. 032 ya emitido -> seguir a 031).
                if _is_error(response, status) and not is_already_applied(response):
                    break

        if is_sequence_successful(sent):
            _mark_rejected(doc)
            result["rejected"] = True
            return result

    # Se agotaron los intentos.
    insert_alert(
        doc.name,
        "No se ha podido rechazar la factura en documenteme. Se reintentara "
        "en la proxima sincronizacion.",
        make_now(),
    )
    result["error"] = "Maximo de intentos alcanzado"
    return result


def _send_event(event, url, headers, method, sender):
    try:
        response, status = sender(
            event["payload"], url, headers, method
        )
        return response, status
    except Exception as error:
        return {"errorInterno": str(error)}, 500


def _mark_rejected(doc):
    doc.nvfac_esta = "R"
    doc.qp_is_event_completed = 1
    doc.nvfac_ueve = "031"
    resolve_open_alerts(doc.name)
    doc.save()


def raw_http(payload, url, headers, method):
    """Envia un evento a documenteme (delega en el adapter, usa requests del modulo)."""
    return _adapter_raw_http(
        payload, url, headers, method, requests_module=requests
    )


# =========================================================================
# Helpers
# =========================================================================
def get_company_tax_id():
    """NIT de la compania del usuario actual (delega en el adapter)."""
    return _adapter_get_company_tax_id(frappe_module=frappe)


def make_now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
