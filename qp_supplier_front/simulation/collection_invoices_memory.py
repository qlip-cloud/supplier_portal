# -*- coding: utf-8 -*-
"""
collection_invoices_memory.py (simulation)
==========================================
Implementacion in-memory del contrato domain/ports/collection_invoices_port.py
sobre simulation/store.MemoryStore. Misma semantica que
resources/collection_accounts/_collection_invoice_base.py pero sin tocar la
base de datos real.

La factura (qp_SP_PurchaseInvoice) se crea en memoria al insertar la cuenta
de cobro (qp_SP_CollectionAccounts) y se evalua a la vez; la aprobacion
actualiza la fila existente (BCC) y marca la cuenta como "Facturado", sin
crear qp_SP_PurchaseInvoiceBC ni eventos.
"""

from qp_supplier_front.simulation.references_memory import (
    memory_get_headquarter,
    memory_get_receipt_bank,
    memory_po_exists,
    memory_resolve_rule,
)
from qp_supplier_front.uses_cases.collection_invoices import mapping

PURCHASE_INVOICE = "qp_SP_PurchaseInvoice"
COLLECTION_ACCOUNT = "qp_SP_CollectionAccounts"
PURCHASE_ORDER = "qp_SP_PurchaseOrder"
PURCHASE_ORDER_ITEM = "qp_SP_PurchaseOrderItem"
NOTIFICATIONS = "qp_SP_PurchaseInvoiceNotification"

GET_DOCS_FIELDS = [
    "name",
    "qp_status",
    "nvfac_fech",
    "nvpro_ndoc",
    "nvfac_nume",
    "nvfac_cufe",
    "nvfac_conv",
    "subtotal",
    "tax",
    "total",
    "currency",
    "purchase_order_id",
    "collection_account",
]


def _now_str():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _now_date():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")


def _set_fields(store, doctype, name, fields):
    """Aplica varios campos como un solo set_value (dict)."""
    for key, value in (fields or {}).items():
        store.set_value(doctype, name, key, value)


def memory_insert_notification(store, parent_name, message, now=None,
                               notification_type="Alerta"):
    if not parent_name or not message:
        return None
    store.insert(NOTIFICATIONS, {
        "parent": parent_name,
        "parenttype": PURCHASE_INVOICE,
        "parentfield": "notifications",
        "notification_date": now or _now_str(),
        "notification_type": notification_type,
        "notification_message": message,
        "status": "Abierta",
    })


def memory_resolve_open_notifications(store, parent_name):
    if not parent_name:
        return
    for row in store.query(NOTIFICATIONS, filters={"parent": parent_name}):
        if row.get("status") == "Abierta":
            store.set_value(NOTIFICATIONS, row["name"], "status", "Resuelta")


def memory_po_available(store, purchase_order):
    """Total disponible de una OC en memoria: grand_total menos lo facturado."""
    po = store.get(PURCHASE_ORDER, purchase_order) or {}
    total_due = float(po.get("grand_total") or 0)
    rows = store.query(
        PURCHASE_INVOICE, filters={"purchase_order_id": purchase_order}
    )
    already_invoiced = sum(float(row.get("total") or 0) for row in rows)
    return total_due, max(total_due - already_invoiced, 0)


def memory_get_po(store, purchase_order):
    return store.get(PURCHASE_ORDER, purchase_order)


def memory_get_first_po_item(store, purchase_order):
    if not purchase_order:
        return None
    rows = store.query(
        PURCHASE_ORDER_ITEM,
        filters={"parent": purchase_order},
        fields=["item_code"],
        order_by="idx asc, name asc",
        limit=1,
    )
    if not rows:
        return None
    return rows[0].get("item_code")


def memory_create_collection_account(store, purchase_order, amount_to_invoice,
                                     observations=None, docs=None):
    """Crea la cuenta de cobro y la factura asociada en memoria."""
    po = memory_get_po(store, purchase_order)
    if not po:
        return {"error": "La orden de compra no existe."}
    total_due, available_amount = memory_po_available(store, purchase_order)
    amount_to_invoice = float(amount_to_invoice or 0)
    if amount_to_invoice <= 0:
        return {"error": "El monto a facturar debe ser mayor a cero."}
    if amount_to_invoice > available_amount:
        return {"error": "El monto a facturar supera el valor disponible."}

    creation_date = _now_date()
    ca_row = {
        "supplier_id": po.get("supplier"),
        "supplier": po.get("supplier"),
        "purchase_order": purchase_order,
        "total_due": total_due,
        "available_amount": available_amount,
        "amount_payable": amount_to_invoice,
        "observations": observations or "",
        "docs": docs or "",
        "status": "Borrador",
        "creation_date": creation_date,
    }
    ca_name = store.insert(COLLECTION_ACCOUNT, ca_row)

    pi_name = memory_create_purchase_invoice(store, ca_name)
    return {
        "name": ca_name,
        "available_amount": available_amount,
        "amount_payable": amount_to_invoice,
        "purchase_invoice": pi_name,
    }


def memory_create_purchase_invoice(store, collection_account_name):
    """Crea el qp_SP_PurchaseInvoice en memoria a partir de la cuenta de
    cobro y lo evalua (V si cumple la regla, E si no)."""
    ca = store.get(COLLECTION_ACCOUNT, collection_account_name) or {}
    po = memory_get_po(store, ca.get("purchase_order")) or {}
    amount_payable = float(ca.get("amount_payable") or 0)
    now = _now_str()

    pi_row = {
        "invoice_id": "",
        "status": "Abierto",
        "qp_status": "E",
        "qp_sync_flow": "COLLECTION",
        "supplier": ca.get("supplier_id"),
        "purchase_order_id": ca.get("purchase_order"),
        "nvpro_ndoc": ca.get("supplier_id"),
        "nvfac_fech": ca.get("creation_date"),
        "nvfac_nume": "",
        "nvfac_cufe": "",
        "nvfac_conv": "1",
        "currency": po.get("currency") or "COP",
        "subtotal": amount_payable,
        "tax": 0,
        "total": amount_payable,
        "collection_account": collection_account_name,
        "registration_date": ca.get("creation_date"),
        "creation": now,
        "modified": now,
    }
    pi_name = store.insert(PURCHASE_INVOICE, pi_row)
    store.set_value(PURCHASE_INVOICE, pi_name, "nvfac_nume", pi_name)
    store.set_value(
        COLLECTION_ACCOUNT, collection_account_name, "purchase_invoice", pi_name
    )

    memory_evaluate_purchase_invoice(store, pi_name)
    return pi_name


def memory_evaluate_purchase_invoice(store, pi_name):
    """Valida la factura (regla OC - recepcion adaptada) y fija V/E."""
    row = store.get(PURCHASE_INVOICE, pi_name) or {}
    if not row:
        return {"ok": False, "warnings": []}
    doc = mapping.build_document_dict(row)
    warnings = mapping.collect_validation_violations(
        [doc],
        lambda po: memory_po_exists(store, po),
        lambda po: memory_get_receipt_bank(store, po),
        resolve_rule_fn=lambda d: memory_resolve_rule(store, d),
    )
    if warnings:
        first = (warnings[0].get("violations") or [""])[0]
        store.set_value(PURCHASE_INVOICE, pi_name, "qp_status", "E")
        store.set_value(PURCHASE_INVOICE, pi_name, "qp_error_message", first)
        memory_insert_notification(store, pi_name, first,
                                   notification_type="ErrorUrgente")
        return {"ok": False, "warnings": warnings}
    store.set_value(PURCHASE_INVOICE, pi_name, "qp_status", "V")
    store.set_value(PURCHASE_INVOICE, pi_name, "qp_error_message", "")
    memory_resolve_open_notifications(store, pi_name)
    return {"ok": True, "warnings": []}


def memory_get_docs(store, doc_names):
    rows = store.query(
        PURCHASE_INVOICE,
        filters={"name": ["in", list(doc_names or [])]},
        fields=GET_DOCS_FIELDS,
    )
    return [mapping.build_document_dict(row) for row in rows]


def memory_get_lines(store, doc):
    purchase_order = doc.get("nvfac_orde")
    if not purchase_order:
        return [], "La factura no tiene orden de compra"
    item_code = memory_get_first_po_item(store, purchase_order)
    if not item_code:
        return [], "La orden de compra no tiene items"
    amount_payable = doc.get("nvfac_totp") or doc.get("nvfac_stot") or 0
    line = mapping.build_single_line(
        {"item_code": item_code},
        amount_payable,
        order_no=purchase_order,
    )
    return [line], ""


def memory_mark_collection_account_invoiced(store, doc):
    account_name = doc.get("collection_account")
    if not account_name:
        return
    current = store.get_value(COLLECTION_ACCOUNT, account_name, "status")
    if current != "Facturado":
        store.set_value(COLLECTION_ACCOUNT, account_name, "status", "Facturado")


def memory_persist_invoice(store, doc, doc_number, now):
    if not doc_number:
        doc_number = doc.get("nvfac_nume") or doc.get("name")
    _set_fields(store, PURCHASE_INVOICE, doc.get("name"), {
        "invoice_id": doc_number,
        "qp_status": "BCC",
        "qp_is_error": 0,
        "qp_error_message": "",
    })
    memory_resolve_open_notifications(store, doc.get("name"))
    memory_mark_collection_account_invoiced(store, doc)
    return doc_number


def memory_mark_registered(store, doc, doc_number=None):
    store.set_value(PURCHASE_INVOICE, doc.get("name"), "qp_status", "BCC")
    memory_resolve_open_notifications(store, doc.get("name"))


def memory_mark_error(store, doc, error):
    _set_fields(store, PURCHASE_INVOICE, doc.get("name"), {
        "qp_is_error": 1,
        "qp_error_message": error,
    })
    memory_insert_notification(store, doc.get("name"), error,
                               notification_type="ErrorUrgente")


def memory_mark_duplicate_registered(store, doc, error, now):
    _set_fields(store, PURCHASE_INVOICE, doc.get("name"), {
        "qp_status": "BCC",
        "qp_is_error": 1,
        "qp_error_message": (
            "La factura ya existe en BC; falta el codigo BC. Error: {}"
        ).format(error),
    })
    memory_insert_notification(
        store, doc.get("name"),
        "La factura ya existe en BC; falta el codigo BC. Error: {}".format(error),
        now=now,
        notification_type="ErrorUrgente",
    )
    memory_mark_collection_account_invoiced(store, doc)


def memory_reject(store, doc_names, motive, is_invoice_error=False):
    for name in (doc_names or []):
        _set_fields(store, PURCHASE_INVOICE, name, {
            "qp_status": "R",
            "qp_motive": motive or "",
            "qp_reject_is_invoice_error": 1 if is_invoice_error else 0,
        })
        memory_resolve_open_notifications(store, name)
        memory_insert_notification(
            store, name,
            "Factura rechazada: {}".format(motive or "Sin motivo"),
            notification_type="Alerta",
        )


def memory_set_confirmation(store, invoice_id, confirmation_id):
    if not invoice_id or not confirmation_id:
        return {"ok": False, "error": "invoice_id y confirmation_id son requeridos"}
    rows = store.query(
        PURCHASE_INVOICE,
        filters={"invoice_id": invoice_id},
        fields=["name"],
        limit=1,
    )
    if not rows:
        return {
            "ok": False,
            "error": "No se encontro una factura con invoice_id {}".format(
                invoice_id
            ),
        }
    _set_fields(store, PURCHASE_INVOICE, rows[0]["name"], {
        "confirmation_id": confirmation_id,
        "qp_status": "A",
    })
    memory_resolve_open_notifications(store, rows[0]["name"])
    return {"ok": True}


def memory_query_purchase_invoices(store, filters=None, fields=None,
                                   order_by=None, start=0, page_length=None):
    return store.query(
        PURCHASE_INVOICE,
        filters=filters or {},
        fields=fields or ["*"],
        order_by=order_by,
        start=start,
        page_length=page_length,
    )