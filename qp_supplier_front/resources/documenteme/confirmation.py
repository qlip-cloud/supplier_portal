# -*- coding: utf-8 -*-
"""
confirmation.py (documenteme) -- infraestructura
================================================
Servicios entrantes para el flujo de confirmacion de facturas documenteme
creadas en BC.

Flujo completo:
  1. La factura se crea en BC y queda en estado "BCC" (Creada en BC), con el
     invoice_id que BC devuelve guardado en qp_SP_PurchaseInvoice.invoice_id,
     y una fila en qp_SP_PurchaseInvoiceBC (name = invoice_id) que referencia
     al PurchaseInvoice.
  2. El proceso externo carga el confirmation_id mediante el PUT estandar de
     Frappe sobre qp_SP_PurchaseInvoiceBC. El hook on_update (on_purchase_
     invoice_bc_update) detecta el cambio de confirmation_id, marca el
     documento en estado "PA" (En proceso de Aprobacion) y encola el job
     asincronico que notifica la aprobacion a documenteme (030 -> 032 -> 033).
  3. update_document se mantiene como fallback para notificar la confirmacion
     por invoice_id sin usar el PUT estandar.
"""

import frappe
from frappe import parse_json

from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.resources.documenteme import auto_approve_confirmation as approval
from qp_supplier_front.uses_cases.documenteme.approve_confirmation import (
    process_confirmation,
)
from qp_supplier_front.uses_cases.documenteme.conversion import is_cash_invoice

PURCHASE_INVOICE = "qp_SP_PurchaseInvoice"
PURCHASE_INVOICE_BC = "qp_SP_PurchaseInvoiceBC"
DOCUMENT_DETAIL = "qp_SP_DocumentDetail"


# =========================================================================
# Callbacks de infraestructura
# =========================================================================
def find_document_by_invoice_id(invoice_id):
    """Localiza el qp_SP_DocumentDetail a partir del invoice_id de BC.

    El invoice_id se guarda en qp_SP_PurchaseInvoice.invoice_id; el
    name de ese registro coincide con el name (nvfac_nume) del
    qp_SP_DocumentDetail.
    """
    if not invoice_id:
        return None
    invoice_name = frappe.get_all(
        PURCHASE_INVOICE,
        filters={"invoice_id": invoice_id},
        pluck="name",
        limit=1,
    )
    if not invoice_name:
        return None
    name = invoice_name[0]
    if not frappe.db.exists(DOCUMENT_DETAIL, name):
        return None
    return {
        "name": name,
        "invoice_id": invoice_id,
    }


def set_confirmation_id(doc, confirmation_id):
    frappe.db.set_value(
        PURCHASE_INVOICE,
        {"invoice_id": doc["invoice_id"]},
        "confirmation_id",
        confirmation_id,
    )


def mark_pending_approval(doc):
    frappe.db.set_value(
        DOCUMENT_DETAIL,
        doc["name"],
        "nvfac_esta",
        "PA",
    )


def enqueue_approve(doc):
    detail = frappe.db.get_value(
        DOCUMENT_DETAIL, doc["name"], ["nvfac_conv"], as_dict=True
    ) or {}
    if is_cash_invoice(detail.get("nvfac_conv")):
        frappe.db.set_value(
            DOCUMENT_DETAIL, doc["name"], {
                "nvfac_esta": "A",
                "qp_is_event_completed": 1,
            }
        )
        from qp_supplier_front.resources.documenteme._alerts import resolve_open_alerts
        resolve_open_alerts(doc["name"])
        return
    approval.enqueue_approve_confirmation(doc["name"])


def _commit():
    frappe.db.commit()


# =========================================================================
# Hook del doctype (disparo por PUT estandar de Frappe sobre el nuevo doctype)
# =========================================================================
def on_purchase_invoice_bc_update(doc, method):
    """Dispara el flujo de aprobacion cuando el confirmation_id se carga.

    Se invoca via doc_events on_update de qp_SP_PurchaseInvoiceBC (lo dispara
    el PUT estandar /api/resource/qp_SP_PurchaseInvoiceBC/<invoice_id>).
    Cuando el confirmation_id pasa de vacio a un valor, marca el documento en
    estado "PA" (En proceso de Aprobacion) y encola el job 030 -> 032 -> 033.

    El name del PurchaseInvoiceBC es el invoice_id que BC devuelve; la
    referencia purchase_invoice apunta al qp_SP_PurchaseInvoice cuyo name
    coincide con el name (nvfac_nume) del qp_SP_DocumentDetail.

    No valida el estado del documento: solo reacciona al cambio de
    confirmation_id (antes vacio, ahora con valor).
    """
    confirmation_id = doc.get("confirmation_id")
    if not confirmation_id:
        return
    before = doc.get_doc_before_save()
    if before and before.get("confirmation_id"):
        return

    document_detail_name = doc.get("purchase_invoice")
    if not document_detail_name:
        return
    if not frappe.db.exists(DOCUMENT_DETAIL, document_detail_name):
        return
    try:
        detail = frappe.db.get_value(
            DOCUMENT_DETAIL, document_detail_name, ["nvfac_conv", "nvfac_esta"], as_dict=True
        ) or {}
        if is_cash_invoice(detail.get("nvfac_conv")):
            frappe.db.set_value(
                DOCUMENT_DETAIL, document_detail_name, {
                    "nvfac_esta": "A",
                    "qp_is_event_completed": 1,
                }
            )
            from qp_supplier_front.resources.documenteme._alerts import resolve_open_alerts
            resolve_open_alerts(document_detail_name)
            frappe.db.commit()
            return
        frappe.db.set_value(DOCUMENT_DETAIL, document_detail_name, "nvfac_esta", "PA")
        approval.enqueue_approve_confirmation(document_detail_name)
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "on_purchase_invoice_bc_update")


# =========================================================================
# Servicios entrantes
# =========================================================================
@frappe.whitelist()
def update_document(invoice_id, confirmation_id=None):
    """Recibe la confirmacion de BC y dispara la aprobacion en documenteme.

    Parametros:
      - invoice_id: numero que BC devuelve al crear la factura (se guarda en
        qp_SP_PurchaseInvoice.invoice_id).
      - confirmation_id: codigo de confirmacion que nos envia BC.
    """
    try:
        result = process_confirmation(
            invoice_id,
            confirmation_id,
            find_document_fn=find_document_by_invoice_id,
            set_confirmation_id_fn=set_confirmation_id,
            mark_pending_approval_fn=mark_pending_approval,
            enqueue_approve_fn=enqueue_approve,
            commit_fn=_commit,
        )

        if not result["ok"]:
            detail = "; ".join(result["errors"])
            response(400, "No se pudo actualizar el documento: {}".format(detail))
            return

        doc = result["doc"]
        frappe.db.commit()
        response(200, "Documento actualizado y aprobacion en proceso",
                 {"name": doc["name"], "invoice_id": doc["invoice_id"]})

    except Exception as error:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "update_document")
        response(500, "Error al actualizar el documento: {}".format(str(error)))
