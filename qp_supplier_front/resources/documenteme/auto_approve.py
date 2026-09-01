# -*- coding: utf-8 -*-
"""
auto_approve.py (documenteme) — infraestructura
==============================================
Aprobacion automatica de facturas documenteme.

Replica el patron de auto_reject.py reutilizando el nucleo puro de
aprobacion (uses_cases/documenteme/approve):

1. Fase analisis: las facturas no definitivas que cumplen la regla
   factura - orden - recepcion (y montos) pasan a estado "V".
2. Fase creacion en BC: las facturas en "V" se envian a BC en lote (un solo
   payload con array) y pasan a estado "BCC" (Creada en BC). La aprobacion
   final ("A") se alcanza cuando el servicio de confirmacion (actualizar_
   documento) guarda el confirmation_id y la notificacion 030 -> 032 -> 033
   a documenteme tiene exito.

Los accesos a datos van por el facade de runtime (real o in-memory); no se
decide simulacion aqui. Si el facade es in-memory el job corre inline (el
store no cruza workers).
"""

import frappe

from qp_supplier_front.resources.documenteme import runtime
from qp_supplier_front.resources.documenteme._approve_base import (
    approve_documents_core,
    po_exists,
    receipt_bank,
)
from qp_supplier_front.resources.documenteme.auto_reject import (
    resolve_rule as _resolve_rule,
)
from qp_supplier_front.uses_cases.documenteme.approve import (
    ANALYSIS_STATES,
    _allocate_registrables,
)
from qp_supplier_front.uses_cases.documenteme.receipt_bank import DEFAULT_EPSILON

AUTO_APPROVE_JOB_METHOD = (
    "qp_supplier_front.resources.documenteme.auto_approve.approve_batch_job"
)


def _data():
    """Facade de datos en simulacion (memoria) o None en modo real."""
    return runtime.resolve().get("data")


def _claimed_invoice_numbers():
    """Facturas con al menos un recibo reclamado manualmente (seleccion en
    curso). Se excluyen del flujo automatico (manual excluye auto)."""
    components = runtime.resolve()
    fn = components.get("claimed_invoice_numbers_fn")
    if fn is None:
        from qp_supplier_front.infrastructure.adapters.receipt_claim_adapter import (
            claimed_invoice_numbers,
        )
        return claimed_invoice_numbers()
    return fn()


def _callbacks():
    return runtime.resolve().get("approve_callbacks") or {}


def _master_setup_source(master_setup=None):
    """Adaptador de config del setup (memoria o real), inyectable."""
    if master_setup is not None:
        return master_setup
    from qp_supplier_front.infrastructure.adapters.master_setup_source import (
        resolve_master_setup_source,
    )
    return resolve_master_setup_source(data=_data(), frappe_module=frappe)


def is_auto_approve_enabled(master_setup=None):
    source = _master_setup_source(master_setup)
    return bool(source.auto_approve_enabled())


def get_analysis_candidates(doc_names=None):
    filters = {
        "nvfac_ueve": ["is", "not set"],
        "nvfac_esta": ["in", ANALYSIS_STATES],
    }
    if doc_names:
        filters["name"] = ["in", list(doc_names)]

    data = _data()
    claimed = _claimed_invoice_numbers()
    if data is None:
        docs = frappe.get_all(
            "qp_SP_DocumentDetail",
            filters=filters,
            fields=[
                "name",
                "nvfac_nume",
                "nvfac_orde",
                "nvfac_rece",
                "nvfac_totp",
                "nvfac_stot",
                "nvfac_esta",
                "nvfac_ueve",
                "nvfac_conv",
            ],
        )
    else:
        docs = data.get_all(
            "qp_SP_DocumentDetail",
            filters=filters,
            fields=[
                "name",
                "nvfac_nume",
                "nvfac_orde",
                "nvfac_rece",
                "nvfac_totp",
                "nvfac_stot",
                "nvfac_esta",
                "nvfac_ueve",
                "nvfac_conv",
            ],
        )
    return [doc for doc in docs if doc.get("nvfac_nume") not in claimed]


def promote_eligible_to_v(doc_names=None):
    """Fase analisis: promueve a "V" solo facturas con combinacion real.

    Reparte el banco cooperativamente por orden de compra (_allocate_registrables,
    el mismo reparto que usa la aprobacion). Solo las facturas que OBTIENEN una
    combinacion exacta de recepciones no consumidas suben a "V"; las perdedoras
    quedan en "E" y seran asignadas por el flujo de asignacion. Si en un ciclo
    posterior llegan recibos que la completan, vuelve a ser candidata y se
    promueve (independientemente de si ya esta asignada: la asignacion no
    bloquea la auto-aprobacion cuando la factura se completa).
    """
    data = _data()
    cb = _callbacks()
    po_ok = cb.get("po_exists_fn", po_exists)
    bank_fn = cb.get("receipt_bank_fn", receipt_bank)
    resolve_rule = cb.get("resolve_rule_fn", _resolve_rule)

    candidates = [
        doc
        for doc in get_analysis_candidates(doc_names)
        if doc.get("nvfac_esta") != "V"
    ]
    valid, _errors, _allocation = _allocate_registrables(
        candidates,
        po_ok,
        bank_fn,
        DEFAULT_EPSILON,
        resolve_rule_fn=resolve_rule,
    )

    promoted = []
    for doc in valid:
        if data is None:
            frappe.db.set_value(
                "qp_SP_DocumentDetail",
                doc.get("name"),
                "nvfac_esta",
                "V",
            )
        else:
            data.set_value(
                "qp_SP_DocumentDetail",
                doc.get("name"),
                "nvfac_esta",
                "V",
            )
        promoted.append(doc.get("nvfac_nume"))
    if data is None:
        frappe.db.commit()
    else:
        data.commit()
    return promoted


def get_v_doc_names(doc_names=None):
    filters = {
        "nvfac_ueve": ["is", "not set"],
        "nvfac_esta": "V",
    }
    if doc_names:
        filters["name"] = ["in", list(doc_names)]

    data = _data()
    if data is None:
        docs = frappe.get_all(
            "qp_SP_DocumentDetail",
            filters=filters,
            fields=["name", "nvfac_nume"],
        )
    else:
        docs = data.get_all(
            "qp_SP_DocumentDetail",
            filters=filters,
            fields=["name", "nvfac_nume"],
        )

    claimed = _claimed_invoice_numbers()
    names = []
    claimed_positions = set()
    for doc in docs:
        if isinstance(doc, dict):
            names.append(doc.get("name"))
            if doc.get("nvfac_nume") in claimed:
                claimed_positions.add(doc.get("name"))
        else:
            names.append(doc)
    return [name for name in names if name not in claimed_positions]


def run_auto_approve(enqueue=True, doc_names=None):
    data = _data()
    if not is_auto_approve_enabled():
        return {"approved": [], "errors": [], "skipped": True}

    promoted = promote_eligible_to_v(doc_names)

    doc_names = get_v_doc_names(doc_names)
    if not doc_names:
        return {"approved": [], "errors": [], "skipped": False}

    if enqueue and (data is None or not data.is_in_memory):
        frappe.enqueue(
            AUTO_APPROVE_JOB_METHOD,
            doc_names=doc_names,
            queue="long",
            timeout=14400,
            job_name="auto approve documents",
        )
        return {
            "approved": [],
            "errors": [],
            "skipped": False,
            "enqueued": len(doc_names),
            "promoted": promoted,
        }

    result = approve_batch_job(doc_names)
    return {
        "approved": result.get("approved", []),
        "errors": result.get("errors", []),
        "skipped": False,
        "promoted": promoted,
    }


def approve_batch_job(doc_names):
    result = approve_documents_core(doc_names)
    data = _data()
    _demote_unregistrable(result, data)
    if data is None:
        frappe.db.commit()
    else:
        data.commit()

    for err in result.get("errors", []):
        frappe.log_error(
            message="Factura {}: {}".format(
                err.get("nvfac_nume"), err.get("error")
            ),
            title="Auto approve - error",
        )

    return result


def _demote_unregistrable(result, data):
    """Red de seguridad: devuelve a "E" facturas "V" sin combinacion de recibos.

    Una factura promovida a "V" que al aprobarse no logra combinacion de
    recepciones (p. ej. otra factura de la misma OC se quedo con los recibos)
    vuelve a "E" (Registrado) en lugar de quedar atascada en "V". No inserta
    alerta: el proximo ciclo la re-evalua y, si llegan recibos que la completen,
    se vuelve a promover y aprobar; mientras tanto queda disponible para que el
    flujo de asignacion la asigne.
    """
    for item in (result.get("unregistrable") or []):
        name = item.get("name")
        if not name:
            continue
        if data is None:
            frappe.db.set_value(
                "qp_SP_DocumentDetail", name, "nvfac_esta", "E"
            )
        else:
            data.set_value(
                "qp_SP_DocumentDetail", name, "nvfac_esta", "E"
            )


@frappe.whitelist()
def auto_approve():
    try:
        result = run_auto_approve()
        _data().commit() if _data() is not None else frappe.db.commit()
        return {"success": True, "data": result}
    except Exception as error:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "auto_approve")
        return {"success": False, "error": str(error)}