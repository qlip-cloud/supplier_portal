# -*- coding: utf-8 -*-
"""
auto_approve.py (documenteme) — infraestructura
===============================================
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

Solo corre si el setup qp_SP_MasterSetup.auto_approve esta habilitado.
El envio se encola como job de fondo para no bloquear el servicio.
"""

import frappe

from qp_supplier_front.resources.documenteme._approve_base import (
    approve_documents_core,
    po_exists,
    receipts_total,
)
from qp_supplier_front.uses_cases.documenteme.approve import (
    ANALYSIS_STATES,
    validate_registrable,
)

AUTO_APPROVE_JOB_METHOD = (
    "qp_supplier_front.resources.documenteme.auto_approve.approve_batch_job"
)


def is_auto_approve_enabled():
    return bool(frappe.db.get_single_value("qp_SP_MasterSetup", "auto_approve"))


def get_analysis_candidates(doc_names=None):
    filters = {
        "nvfac_ueve": ["is", "not set"],
        "nvfac_esta": ["in", ANALYSIS_STATES],
    }
    if doc_names:
        filters["name"] = ["in", list(doc_names)]

    return frappe.get_all(
        "qp_SP_DocumentDetail",
        filters=filters,
        fields=[
            "name",
            "nvfac_nume",
            "nvfac_orde",
            "nvfac_rece",
            "nvfac_totp",
            "nvfac_esta",
            "nvfac_ueve",
            "nvfac_conv",
        ],
    )


def promote_eligible_to_v(doc_names=None):
    promoted = []
    for doc in get_analysis_candidates(doc_names):
        ok, _ = validate_registrable(doc, po_exists, receipts_total)
        if ok and doc.get("nvfac_esta") != "V":
            frappe.db.set_value(
                "qp_SP_DocumentDetail",
                doc.get("name"),
                "nvfac_esta",
                "V",
            )
            promoted.append(doc.get("nvfac_nume"))
    frappe.db.commit()
    return promoted


def get_v_doc_names(doc_names=None):
    filters = {
        "nvfac_ueve": ["is", "not set"],
        "nvfac_esta": "V",
    }
    if doc_names:
        filters["name"] = ["in", list(doc_names)]

    return frappe.get_all(
        "qp_SP_DocumentDetail",
        filters=filters,
        pluck="name",
    )


def run_auto_approve(enqueue=True, doc_names=None):
    if not is_auto_approve_enabled():
        return {"approved": [], "errors": [], "skipped": True}

    promoted = promote_eligible_to_v(doc_names)

    doc_names = get_v_doc_names(doc_names)
    if not doc_names:
        return {"approved": [], "errors": [], "skipped": False}

    if enqueue:
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
    frappe.db.commit()

    for err in result.get("errors", []):
        frappe.log_error(
            message="Factura {}: {}".format(
                err.get("nvfac_nume"), err.get("error")
            ),
            title="Auto approve - error",
        )

    return result


@frappe.whitelist()
def auto_approve():
    try:
        result = run_auto_approve()
        frappe.db.commit()
        return {"success": True, "data": result}
    except Exception as error:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "auto_approve")
        return {"success": False, "error": str(error)}
