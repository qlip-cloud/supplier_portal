# -*- coding: utf-8 -*-
"""
auto_assign.py (resources/collection_accounts)
==============================================
Cableado de la asignacion automatica de las facturas de cuentas de cobro
(qp_SP_PurchaseInvoice), espejo de resources/documenteme/auto_assign.py pero
sobre qp_SP_PurchaseInvoice.

Reutiliza el nucleo puro uses_cases/documenteme/auto_assign.auto_assign: las
facturas de collection son de CREDITO (nvfac_conv="2"), por lo que la rama
credito (should_auto_assign) aplica: una factura con OC que no esta cubierta
por una combinacion exacta de recepciones no consumidas se asigna a los
usuarios configurados.
"""

import frappe

from qp_supplier_front.resources.collection_accounts._collection_invoice_base import (
    receipt_bank as _receipt_bank,
)
from qp_supplier_front.resources.documenteme.auto_assign import (
    _load_assignment_rows,
    get_assignee_emails,
    resolve_assignee_users,
)
from qp_supplier_front.uses_cases.documenteme.auto_assign import (
    auto_assign as auto_assign_core,
)

PURCHASE_INVOICE = "qp_SP_PurchaseInvoice"
ASSIGNED_USERS_CHILD = "qp_SP_PurchaseInvoiceAssignedUser"
INVOICE_STATES_QUEUE = ("E",)


def run_collection_auto_assign(doc_names=None):
    return auto_assign_core(
        candidates_fn=get_candidates,
        get_oc_context_fn=get_oc_context,
        get_receipt_bank_fn=_receipt_bank,
        resolve_emails_fn=get_assignee_emails,
        resolve_users_fn=resolve_assignee_users,
        add_assignees_fn=add_assignees,
        doc_names=doc_names,
    )


def get_candidates(doc_names=None):
    filters = {
        "qp_sync_flow": "COLLECTION",
        "qp_status": ["in", list(INVOICE_STATES_QUEUE)],
    }
    if doc_names:
        filters["name"] = ["in", list(doc_names)]

    docs = frappe.get_all(
        PURCHASE_INVOICE,
        filters=filters,
        fields=[
            "name",
            "nvfac_nume",
            "purchase_order_id",
            "subtotal",
            "total",
            "collection_account",
        ],
    )

    candidates = []
    for doc in docs:
        has_assigned_users = bool(frappe.db.exists(ASSIGNED_USERS_CHILD, {
            "parent": doc.get("name"),
            "parenttype": PURCHASE_INVOICE,
        }))
        if has_assigned_users:
            continue
        candidates.append({
            "name": doc.get("name"),
            "nvfac_nume": doc.get("nvfac_nume") or doc.get("name"),
            "nvfac_orde": doc.get("purchase_order_id"),
            "nvfac_totp": doc.get("total") or 0,
            "nvfac_stot": doc.get("subtotal") or 0,
            "nvfac_conv": "2",
            "assigned_to": None,
            "has_assigned_users": False,
            "in_queue": True,
        })

    return candidates


def get_oc_context(purchase_order_number):
    if not purchase_order_number:
        return None

    if not frappe.db.exists("Purchase Order", purchase_order_number):
        return None

    values = frappe.db.get_value(
        "Purchase Order",
        purchase_order_number,
        ["qp_oc_type", "qp_headquarter", "qp_order_confirmation_no"],
    )
    if values is None:
        return None

    if values[2] != purchase_order_number:
        return None

    return {"oc_type": values[0], "headquarter": values[1]}


def add_assignees(purchase_invoice_name, users):
    """Agrega usuarios asignados a la factura (child assigned_users).

    Idempotente: no duplica usuarios ya presentes.
    """
    invoice = frappe.get_doc(PURCHASE_INVOICE, purchase_invoice_name)
    existing = {row.user for row in invoice.assigned_users}

    for user in (users or []):
        if not user or user in existing:
            continue
        invoice.append("assigned_users", {"user": user})

    invoice.save(ignore_permissions=True)