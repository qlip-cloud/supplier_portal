# -*- coding: utf-8 -*-
"""
_approve_base.py (documenteme)
==============================
Cablea el nucleo puro de aprobacion (uses_cases/documenteme/approve) con
implementaciones Frappe. Es el equivalente de _reject_base.py para el
rechazo y sirve a los flujos manual (resources/documenteme/approve.py) y
automatico (resources/documenteme/auto_approve.py).
"""

import frappe
from frappe import parse_json

from qp_supplier_front.resources.documenteme._alerts import (
    insert_alert,
    resolve_open_alerts,
)
from qp_supplier_front.resources.documenteme import simulation
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.services.role_resolver import get_active_role
from qp_supplier_front.uses_cases.documenteme.approve import (
    approve_documents,
)

ALLOWED_ROLES = {"Administrador Documenteme", "Administrador Sede Documenteme"}


def _has_permission(user_roles):
    active = get_active_role(user_roles)
    return active in ALLOWED_ROLES


def _make_now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# =========================================================================
# Callbacks de infraestructura
# =========================================================================
def get_docs(doc_names):
    return frappe.get_all(
        "qp_SP_DocumentDetail",
        filters={"name": ["in", list(doc_names)]},
        fields=[
            "name",
            "nvfac_nume",
            "nvpro_ndoc",
            "nvfac_fech",
            "nvfac_cufe",
            "nvtip_docu",
            "nvfac_fpag",
            "nvfac_orde",
            "nvfac_rece",
            "nvfac_totp",
            "nvfac_esta",
            "nvfac_ueve",
            "nvmon_codi",
            "nvfac_stot",
            "nvfac_viva",
            "nvpro_nomb",
        ],
    )


def get_lines(purchase_order):
    if not purchase_order:
        return []
    receipts = frappe.get_all(
        "Purchase Receipt",
        filters={"qp_supplier_oc": purchase_order},
        pluck="name",
    )
    if not receipts:
        return []
    items = frappe.get_all(
        "Purchase Receipt Item",
        filters={"parent": ["in", receipts], "parenttype": "Purchase Receipt"},
        fields=["parent", "item_code", "qty", "rate", "idx"],
        order_by="parent, idx",
    )
    return [
        {
            "item_code": item.get("item_code"),
            "qty": item.get("qty"),
            "rate": item.get("rate"),
            "idx": item.get("idx") or 0,
            "receiving_no": item.get("parent") or "",
            "order_no": purchase_order,
        }
        for item in items
    ]


def po_exists(purchase_order):
    if not purchase_order:
        return False
    return bool(frappe.db.exists("Purchase Order", purchase_order))


def receipts_total(purchase_order):
    if not purchase_order:
        return None
    receipts = frappe.get_all(
        "Purchase Receipt",
        filters={"qp_supplier_oc": purchase_order},
        fields=["total"],
    )
    if not receipts:
        return None
    return sum(receipt.get("total") or 0 for receipt in receipts)


def get_supplier_by_tax_id(tax_id):
    if not tax_id:
        return None
    suppliers = frappe.get_all(
        "Supplier",
        filters={"tax_id": tax_id},
        pluck="name",
        limit=1,
    )
    return suppliers[0] if suppliers else None


def parse_doc_numbers(response):
    """Resultados por factura: lista de {doc_number, error} en el mismo
    orden del payload enviado a BC."""
    if not isinstance(response, dict):
        return []
    return response.get("invoices") or []


def resolve_doc_number_via_odata(doc):
    from qp_supplier_front.infrastructure.adapters.fetch_oauth_adapter import (
        fetch_invoices,
    )

    vendor = doc.get("nvpro_ndoc")
    if not vendor:
        return None
    invoice_date = str(doc.get("nvfac_fech") or "")[:10]
    param = "$filter=Vendor_No eq '{}' and Document_Type eq 'Invoice'".format(vendor)
    if invoice_date:
        param += " and Posting_Date eq {}".format(invoice_date)
    try:
        result = fetch_invoices("list_purchase_invoice", param=param)
    except Exception:
        return None
    values = result.get("value") or []
    if not values:
        return None
    return values[0].get("Document_No")


def persist_invoice(doc, doc_number, now):
    from qp_supplier_front.infrastructure.adapters.filter_adapter import (
        get_existing_ids,
    )
    from qp_supplier_front.infrastructure.strategies.gp.persist_adapter import (
        insert_invoices,
    )

    if not doc_number:
        doc_number = resolve_doc_number_via_odata(doc)
    if not doc_number:
        doc_number = doc.get("nvfac_nume") or doc.get("name")

    existing = get_existing_ids("qp_SP_PurchaseInvoice", "invoice_id", {doc_number})
    if doc_number in existing:
        return doc_number

    supplier = get_supplier_by_tax_id(doc.get("nvpro_ndoc"))
    invoice_date = str(doc.get("nvfac_fech") or "")[:10]

    invoice_tuple = (
        doc.get("name"),
        doc_number,
        "Abierto",
        invoice_date or None,
        now[:10],
        doc.get("nvmon_codi") or "COP",
        doc.get("nvfac_stot") or 0,
        doc.get("nvfac_viva") or 0,
        doc.get("nvfac_totp") or 0,
        supplier,
        doc.get("nvfac_nume") or "",
        doc.get("nvfac_orde") or "",
        "BC",
        now,
        now,
        "Administrator",
        "Administrator",
    )
    insert_invoices({doc.get("name"): invoice_tuple}, now)

    _create_purchase_invoice_bc(doc_number, doc.get("name"))
    return doc_number


def _create_purchase_invoice_bc(doc_number, document_detail_name):
    """Inserta la referencia BC -> PurchaseInvoice para el flujo de confirmacion.

    El nuevo doctype qp_SP_PurchaseInvoiceBC usa como name el codigo que BC
    devuelve (invoice_id) y referencia al qp_SP_PurchaseInvoice. El proceso
    externo completara el confirmation_id mediante el PUT estandar de Frappe.
    """
    if not doc_number or not document_detail_name:
        return
    if frappe.db.exists("qp_SP_PurchaseInvoiceBC", doc_number):
        return
    bc_doc = frappe.get_doc({
        "doctype": "qp_SP_PurchaseInvoiceBC",
        "invoice_id": doc_number,
        "purchase_invoice": document_detail_name,
    })
    bc_doc.insert(ignore_permissions=True)


def mark_registered(doc, doc_number):
    frappe.db.set_value(
        "qp_SP_DocumentDetail",
        doc.get("name"),
        "nvfac_esta",
        "BCC",
    )
    doc["nvfac_esta"] = "BCC"
    resolve_open_alerts(doc.get("name"))


def mark_error(doc, error):
    insert_alert(doc.get("name"), error, _make_now())


def send_purchase_invoice_request(endpoint_code, payload):
    response = frappe.call(
        "qp_middleware.qp_middleware.service.purchase_invoice.sync.create_purchase_invoices",
        payload=payload,
        endpoint_code=endpoint_code,
    )
    try:
        import html

        from qp_supplier_front.services.utils import add_log

        raw_response = None
        log_response = response
        if isinstance(response, dict) and response.get("raw_response") is not None:
            raw_response = html.unescape(response.get("raw_response") or "")
            log_response = dict(response)
            log_response.pop("raw_response", None)

        add_log(
            title="Aprobacion documenteme -> BC ({})".format(endpoint_code),
            payload=payload,
            response=log_response,
            raw_response=raw_response,
        )
    except Exception:
        pass
    return response, 200


# =========================================================================
# Orquestacion compartida
# =========================================================================
def approve_documents_core(doc_names, send_request_fn=None):
    if send_request_fn is None:
        send_request_fn = (
            simulation.send_purchase_invoice_request
            if simulation.is_simulation_enabled()
            else send_purchase_invoice_request
        )
    return approve_documents(
        doc_names,
        get_docs_fn=get_docs,
        get_lines_fn=get_lines,
        po_exists_fn=po_exists,
        receipts_total_fn=receipts_total,
        send_request_fn=send_request_fn or send_purchase_invoice_request,
        parse_doc_numbers_fn=parse_doc_numbers,
        persist_invoice_fn=persist_invoice,
        mark_registered_fn=mark_registered,
        mark_error_fn=mark_error,
        commit_fn=frappe.db.commit,
        now=_make_now(),
    )


def run_approve(doc_names_raw, send_request_fn=None):
    """Flujo manual: valida permisos y aprueba el lote seleccionado."""
    doc_names = parse_json(doc_names_raw)

    if not _has_permission(frappe.get_roles()):
        response(403, "No tiene permisos para aprobar facturas")
        return

    result = approve_documents_core(doc_names, send_request_fn=send_request_fn)
    frappe.db.commit()

    errors = result.get("errors") or []

    for err in errors:
        frappe.log_error(
            message="Factura {}: {}".format(
                err.get("nvfac_nume"), err.get("error")
            ),
            title="Aprobar documenteme - error",
        )

    if errors:
        detail = ", ".join(
            "{}: {}".format(err.get("nvfac_nume"), err.get("error"))
            for err in errors
        )
        response(500, "Error al aprobar: {}".format(detail))
        return

    response(200, "Factura(s) aprobada(s) correctamente", result)
