"""
auto_reject.py (documenteme) — infraestructura
==============================================
Cablea el nucleo puro de rechazo automatico (uses_cases/documenteme/auto_reject)
con implementaciones Frappe y orquesta la notificacion a documenteme.

El rechazo es ASINCRONO y usa un estado intermedio "En proceso" (PR):

1. run_auto_reject() escanea facturas pendientes (nuevas en "E" y las que ya
   quedaron en "PR") y resuelve la regla por proveedor con fallback al setup.
2. Cada factura pasa a "PR" y se marca con la secuencia de eventos en curso
   ("R") y el primer evento pendiente ("030").
3. Se envia UN evento por job (event_job.run_documenteme_event): 030 -> 032
   -> 031. El job hace un solo HTTP, libera el worker y deja el proximo
   evento programado en la factura (qp_event_next_at). El dispatcher
   (event_dispatch, cron por minuto) materializa los vencidos.
4. Si la secuencia completa tiene exito, la factura se marca "R" y se
   resuelven sus alertas. Si se agotan los intentos (fallos acumulados, sin
   resetear con exitos intermedios), se inserta una alerta y la factura
   permanece en "PR" (mientras qp_reject_retry_enabled=1).
5. Kill-switch POR FACTURA: si qp_reject_retry_enabled=0, ese documento no
   envia peticiones aunque este en "PR".
"""

import frappe
import requests

from qp_supplier_front.infrastructure.adapters.documenteme_http_adapter import (
    get_company_tax_id as _adapter_get_company_tax_id,
    get_receipt_total,
    raw_http as _adapter_raw_http,
)
from qp_supplier_front.resources.documenteme.event_job import (
    initialize_event_schedule,
    schedule_event,
)
from qp_supplier_front.uses_cases.documenteme.auto_reject import (
    auto_reject as auto_reject_core,
    resolve_auto_reject_config,
)
from qp_supplier_front.uses_cases.documenteme.conversion import is_cash_invoice
from qp_supplier_front.uses_cases.documenteme.reject_retry import (
    REJECT_PENDING_STATES,
)

REJECT_JOB_METHOD = "qp_supplier_front.resources.documenteme.auto_reject.reject_batch_job"

EVENT_CONFIG = {"031": {"nvfac_esta": "R"}}


def _master_setup_source(master_setup=None):
    """Adaptador de config del setup (real por defecto), inyectable."""
    if master_setup is not None:
        return master_setup
    from qp_supplier_front.infrastructure.adapters.master_setup_source import (
        RealMasterSetupSource,
    )
    return RealMasterSetupSource(frappe_module=frappe)


def get_reject_config(master_setup=None):
    """Configuracion global de reintentos desde qp_SP_MasterSetup."""
    return _master_setup_source(master_setup).reject_config()


def run_auto_reject(http_fn=None, enqueue=True, doc_names=None):
    rejects = auto_reject_core(
        candidates_fn=get_candidates,
        resolve_rule_fn=resolve_rule,
        po_exists_fn=po_exists,
        receipt_for_po_fn=receipt_for_po,
        doc_names=doc_names,
        po_supplier_match_fn=_po_supplier_match,
    )

    # Guard / kill-switch: los docs con retry deshabilitado no se envian.
    rejects = [r for r in rejects if _retry_enabled_for(r["doc"])]

    # Facturas de contado: NO se rechazan por la regla de rechazo. Si la
    # incumplen se ASIGNAN (auto_assign resuelve destinatarios, incl. la fila
    # catch-all para contado sin OC) y su aprobacion queda bloqueada
    # (validate_registrable con resolve_rule_fn). Se excluyen del rechazo.
    rejects = [r for r in rejects if not is_cash_invoice(r.get("nvfac_conv"))]

    _mark_pending(rejects)
    frappe.db.commit()

    # Un job de UN evento por factura (el dispatcher materializa los
    # siguientes). Ya no se encola un batch largo con sleeps.
    for reject in rejects:
        schedule_event(reject["doc"], http_fn=http_fn, enqueue=enqueue)

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
        initialize_event_schedule(doc, "R")
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
    from qp_supplier_front.infrastructure.adapters.receipt_claim_adapter import (
        claimed_invoice_numbers,
    )

    filters = {
        "nvfac_ueve": ["is", "not set"],
        "nvfac_esta": ["in", list(REJECT_PENDING_STATES)],
    }
    if doc_names:
        filters["name"] = ["in", list(doc_names)]

    docs = frappe.get_all(
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
            "nvfac_conv",
            "nvtip_docu",
        ],
    )

    # Seleccion manual en curso (recibos reclamados): se excluye del rechazo
    # automatico (manual excluye auto).
    claimed = claimed_invoice_numbers()
    return [
        doc for doc in docs if doc.get("nvfac_nume") not in claimed
    ]


def resolve_rule(doc, master_setup=None):
    if _is_service_supplier_doc(doc):
        # Para proveedores de servicio (flujo GP) no aplica el default global
        # de rechazo del MasterSetup: solo la regla del proveedor decide.
        return get_supplier_rule(doc.get("nvpro_ndoc"))
    supplier_rule = get_supplier_rule(doc.get("nvpro_ndoc"))
    setup_rule = get_setup_default_rule(master_setup=master_setup)
    return resolve_auto_reject_config(supplier_rule, setup_rule)


def _is_service_supplier_doc(doc):
    """True si el proveedor de la factura tiene qp_is_service_supplier=1.

    Import lazy para evitar el ciclo _approbe_base <-> auto_reject.
    """
    from qp_supplier_front.resources.documenteme._approve_base import (
        is_service_supplier,
    )
    return is_service_supplier(doc.get("nvpro_ndoc"))


def _po_supplier_match(doc):
    """True si la OC existe y pertenece al mismo proveedor de la factura.

    Import lazy para evitar el ciclo _approbe_base <-> auto_reject.
    """
    from qp_supplier_front.resources.documenteme._approve_base import (
        po_supplier_match,
    )
    return po_supplier_match(doc)


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


def get_setup_default_rule(master_setup=None):
    rule_name = _master_setup_source(master_setup).auto_reject_rule()
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
# Rechazo: programacion de eventos (un evento por job)
# =========================================================================
def reject_batch_job(rejects, http_fn=None):
    """Compatibilidad: programa UN evento por factura (sin sleeps).

    El envio de la secuencia 030/032/031 ahora lo materializa
    event_job/event_dispatch (un evento por job, con la espera entre eventos
    persistida en el documento). Se conserva el nombre para callers/tests.
    """
    results = []
    for item in (rejects or []):
        doc_name = item.get("doc") if isinstance(item, dict) else item
        results.append((doc_name, schedule_event(doc_name, http_fn=http_fn)))
    return results


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
