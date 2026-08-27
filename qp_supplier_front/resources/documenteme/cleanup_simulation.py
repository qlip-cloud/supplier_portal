# -*- coding: utf-8 -*-
"""
cleanup_simulation.py (documenteme)
===================================
Limpieza manual de los datos persistidos por el modo simulador.

Identifica las filas simuladas por convencion (sin campo nuevo, para no
requerir bench migrate):

- NIT simulado "999999999" (simulation.SIMULATED_COMPANY_TAX_ID) en
  qp_SP_DocumentSyncLog.tax_id y en el nvpro_ndoc de
  qp_SP_DocumentSyncLine / qp_SP_DocumentDetail.
- invoice_id con prefijo "SIM" en qp_SP_PurchaseInvoice /
  qp_SP_PurchaseInvoiceBC.

Borra en cascada los child rows y los File adjuntos, en orden seguro.

Idempotente: una segunda ejecucion devuelve contadores en cero.
No toca datos reales (NIT != 999999999, invoice_id sin prefijo SIM).
"""

import frappe

from qp_supplier_front.resources.documenteme import simulation
from qp_supplier_front.resources.response import handler as response

SIM_NIT = simulation.SIMULATED_COMPANY_TAX_ID
SIM_PREFIX = "SIM"

DOCUMENT_DETAIL = "qp_SP_DocumentDetail"
SYNC_LINE = "qp_SP_DocumentSyncLine"
SYNC_LOG = "qp_SP_DocumentSyncLog"
PURCHASE_INVOICE = "qp_SP_PurchaseInvoice"
PURCHASE_INVOICE_BC = "qp_SP_PurchaseInvoiceBC"


def _sim_invoice_ids(doctype):
    return frappe.get_all(
        doctype,
        filters={"invoice_id": ["like", "{}-%".format(SIM_PREFIX)]},
        pluck="name",
    )


def _delete_files_of_detail(detail_name):
    """Borra los File de qp_SP_DocumentAttach del detalle antes del parent."""
    file_ids = frappe.db.sql_list(
        "SELECT file_id FROM `tabqp_SP_DocumentAttach` WHERE parent=%s",
        detail_name,
    )
    for file_id in (file_ids or []):
        if file_id:
            try:
                frappe.delete_doc("File", file_id, ignore_permissions=True, force=True)
            except Exception:
                continue


def _delete_document_details():
    names = frappe.get_all(
        DOCUMENT_DETAIL,
        filters={"nvpro_ndoc": SIM_NIT},
        pluck="name",
    )
    count = 0
    for name in names:
        _delete_files_of_detail(name)
        frappe.delete_doc(DOCUMENT_DETAIL, name, ignore_permissions=True, force=True)
        count += 1
    return count


def _delete_sync_lines():
    names = frappe.get_all(
        SYNC_LINE,
        filters={"nvpro_ndoc": SIM_NIT},
        pluck="name",
    )
    count = 0
    for name in names:
        frappe.delete_doc(SYNC_LINE, name, ignore_permissions=True, force=True)
        count += 1
    return count


def _delete_sync_logs():
    names = frappe.get_all(
        SYNC_LOG,
        filters={"tax_id": SIM_NIT},
        pluck="name",
    )
    count = 0
    for name in names:
        frappe.delete_doc(SYNC_LOG, name, ignore_permissions=True, force=True)
        count += 1
    return count


def _delete_purchase_invoices():
    count = 0
    for name in _sim_invoice_ids(PURCHASE_INVOICE):
        frappe.delete_doc(PURCHASE_INVOICE, name, ignore_permissions=True, force=True)
        count += 1
    return count


def _delete_purchase_invoice_bc():
    names = frappe.get_all(
        PURCHASE_INVOICE_BC,
        filters={"invoice_id": ["like", "{}-%".format(SIM_PREFIX)]},
        pluck="name",
    )
    count = 0
    for name in names:
        frappe.delete_doc(PURCHASE_INVOICE_BC, name, ignore_permissions=True, force=True)
        count += 1
    return count


def _run_cleanup():
    """Borra todas las filas simuladas identificadas por convencion.

    Retorna un dict con los contadores por doctype. Orden seguro:
    PurchaseInvoiceBC primero (no tiene dependencias), luego los File/
    detalles, luego PurchaseInvoice, SyncLine, SyncLog.
    """
    deleted = {
        "document_details": 0,
        "sync_lines": 0,
        "sync_logs": 0,
        "purchase_invoices": 0,
        "purchase_invoice_bc": 0,
    }

    deleted["purchase_invoice_bc"] = _delete_purchase_invoice_bc()
    deleted["document_details"] = _delete_document_details()
    deleted["purchase_invoices"] = _delete_purchase_invoices()
    deleted["sync_lines"] = _delete_sync_lines()
    deleted["sync_logs"] = _delete_sync_logs()

    frappe.db.commit()
    return deleted


@frappe.whitelist()
def cleanup_simulated_data():
    deleted = _run_cleanup()
    response(200, "Datos simulados eliminados", deleted)
    return deleted