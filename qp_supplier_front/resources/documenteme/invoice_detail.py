# -*- coding: utf-8 -*-
"""
invoice_detail.py (documenteme)
===============================
Detalle completo (ordenes de compra + recepciones) de una factura para el
modal "Ver detalle". Se usa cuando la factura supera los limites de render
inline (muchas OC o muchas recepciones).

- Aplica el mismo filtro de acceso que el listado (asignacion por sede).
- Reusa enrich_document_list con include_products=True para traer productos,
  precios y el banco de recepciones completo.
- El markup de las dos columnas vive en partials compartidos con la fila.
"""

import frappe

from qp_supplier_front.resources.documenteme import runtime
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.services.documenteme_access import (
    get_assigned_sync_line_names,
    get_assigned_sync_lines_filters,
)
from qp_supplier_front.services.enrich_document_list import enrich_document_list
from qp_supplier_front.services.pagination import get_paginated_filtered

DOCTYPE = "qp_SP_DocumentDetail"


def _resolve_doc(doc_name, data):
    filters = get_assigned_sync_lines_filters(
        frappe.get_roles(),
        frappe.session.user,
        lambda user: get_assigned_sync_line_names(user, data=data),
        {"name": doc_name},
    )
    docs = get_paginated_filtered(0, DOCTYPE, "creation", filters, data=data)
    return next((row for row in docs if row.get("name") == doc_name), None)


@frappe.whitelist()
def get_detail(doc_name, tab="orders"):
    """HTML del cuerpo del modal (pestanas Ordenes / Recepciones)."""
    try:
        if not doc_name:
            response(400, "Falta el documento")
            return

        data = runtime.resolve().get("data")
        doc = _resolve_doc(doc_name, data)
        if not doc:
            response(403, "No tiene acceso a la factura")
            return

        enrich_document_list(
            [doc], DOCTYPE, data=data, include_products=True)

        html = frappe.render_template(
            "qp_supplier_front/templates/modal/invoice_detail_body.html",
            {
                "detail": doc,
                "tab": "receipts" if tab == "receipts" else "orders",
            },
        )
        response(200, "ok", html)

    except Exception as error:
        frappe.db.rollback()
        response(
            500,
            "Error al cargar el detalle de la factura: {}".format(str(error)),
        )
