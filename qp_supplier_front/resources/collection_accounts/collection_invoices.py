# -*- coding: utf-8 -*-
"""
collection_invoices.py (resources/collection_accounts)
======================================================
Servicios @frappe.whitelist() del flujo de facturas de cuentas de cobro
(qp_SP_CollectionAccounts -> qp_SP_PurchaseInvoice).

Endpoints:
  - validate(doc_names): pre-validacion sin efectos secundarios (devuelve las
    violaciones de la regla OC - recepcion para el confirm del front).
  - approve(doc_names, force): aprueba el lote (crea en BC y marca "BCC",
    cuenta de cobro "Facturado"). Con force=True se omiten las advertencias.
  - reject(doc_names, motive, is_invoice_error): rechazo sincrono -> "R".
  - update_confirmation(invoice_id, confirmation_id): confirmacion externa de
    BC -> "A" (sin eventos a documenteme).
  - render_more(page, doctype, order_by, filters): paginacion del front.

Todo el cableado de datos pasa por runtime.resolve(): en modo simulador se
ejecuta en memoria, en modo real con Frappe.
"""

import json

import frappe
from frappe import parse_json

from qp_supplier_front.resources.collection_accounts import (
    _collection_invoice_base as base,
)
from qp_supplier_front.resources.collection_accounts import runtime
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.services.pagination import get_paginated_filtered

NOTIFICATIONS = "qp_SP_PurchaseInvoiceNotification"


def _has_permission():
    return base._has_permission(frappe.get_roles())


@frappe.whitelist()
def validate(doc_names):
    try:
        if not _has_permission():
            response(403, "No tiene permisos para aprobar facturas")
            return

        violation_docs = base.collect_document_violations(parse_json(doc_names))
        response(200, "ok", {"violations": violation_docs})

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al validar: {}".format(str(error)))


@frappe.whitelist()
def approve(doc_names, force=False):
    try:
        force = parse_json(force) if force else False

        result = base.approve_collection_invoices_core(
            parse_json(doc_names), force=force
        )
        frappe.db.commit()

        errors = result.get("errors") or []

        if errors:
            detail = ", ".join(
                "{}: {}".format(err.get("nvfac_nume"), err.get("error"))
                for err in errors
            )
            response(500, "Error al aprobar: {}".format(detail), result)
            return

        response(200, "Factura(s) aprobada(s) correctamente", result)

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al aprobar: {}".format(str(error)))


@frappe.whitelist()
def reject(doc_names, motive, is_invoice_error):
    try:
        if not _has_permission():
            response(403, "No tiene permisos para rechazar facturas")
            return

        names = parse_json(doc_names)
        is_invoice_error = parse_json(is_invoice_error) if is_invoice_error else False

        components = runtime.resolve()
        if components.get("data") is not None and components.get("reject_fn"):
            components["reject_fn"](names, motive, is_invoice_error)
        else:
            base.reject(names, motive, is_invoice_error)

        response(200, "Factura(s) rechazada(s) correctamente")

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al rechazar: {}".format(str(error)))


@frappe.whitelist()
def update_confirmation(invoice_id, confirmation_id=None):
    try:
        components = runtime.resolve()
        if components.get("data") is not None and components.get("set_confirmation_fn"):
            result = components["set_confirmation_fn"](invoice_id, confirmation_id)
        else:
            result = base.set_confirmation(invoice_id, confirmation_id)

        if not result.get("ok"):
            response(400, "No se pudo actualizar: {}".format(result.get("error")))
            return

        frappe.db.commit()
        response(200, "Factura confirmada y aprobada", {"invoice_id": invoice_id})

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al confirmar: {}".format(str(error)))


@frappe.whitelist()
def render_more(page, doctype, order_by, filters=None):
    try:
        parsed_filters = json.loads(filters) if filters else {}
        data = runtime.resolve().get("data")

        rows = get_paginated_filtered(
            int(page), doctype, order_by, parsed_filters, data=data
        )

        base.attach_notification_info(rows, data=data)
        base.attach_reception_info(rows, data=data)
        base.attach_assignment_info(rows, data=data)
        base.attach_document_info(rows, data=data)
        base.attach_comment_info(rows, data=data)

        template = frappe.render_template(
            "qp_supplier_front/templates/list/purchase_invoice_collection/list.html",
            {
                "purchase_invoice_collection": rows,
                "key": "purchase_invoice_collection",
                "doctype": doctype,
                "is_documenteme_admin": _has_permission(),
            },
        )

        response(200, "ok", template)

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al paginar: {}".format(str(error)))


def _get_references(data):
    """Adaptador de referencias de compras (real o memoria segun data)."""
    if data is not None:
        return data.references
    from qp_supplier_front.infrastructure.adapters.reference_source import (
        RealReferenceSource,
    )
    return RealReferenceSource()


@frappe.whitelist()
def render_detail(doc_name):
    """Detalle expandible de una factura de cuenta de cobro.

    Devuelve el HTML con tres tablas: la factura (detalle), los items de la
    orden de compra (OC) y las recepciones asociadas a la OC. Funciona en modo
    real (frappe) y en modo simulador (data facade/memoria) via el adaptador
    de referencias.
    """
    try:
        if not doc_name:
            response(400, "Falta el documento")
            return

        data = runtime.resolve().get("data")
        refs = _get_references(data)

        if data is not None:
            invoice = data.get_value("qp_SP_PurchaseInvoice", doc_name) or {}
        else:
            invoice = frappe.db.get_value(
                "qp_SP_PurchaseInvoice", doc_name, [
                    "name", "nvfac_nume", "purchase_order_id", "supplier",
                    "nvpro_ndoc", "subtotal", "tax", "total", "currency",
                    "qp_status", "collection_account",
                ], as_dict=True
            ) or {}

        purchase_order = invoice.get("purchase_order_id") or ""

        detail_oc = refs.po_items(purchase_order) or []
        receipts = refs.receipts_for(purchase_order) or []
        receipt_names = [r.get("name") for r in receipts if r.get("name")]
        detail_receipt = refs.receipt_items_for(receipt_names) or []

        template = frappe.render_template(
            "qp_supplier_front/templates/list/purchase_invoice_collection/list_detail.html",
            {
                "parent": invoice,
                "detail_oc": detail_oc,
                "detail_receipt": detail_receipt,
                "show_result": True,
            },
        )

        response(200, "ok", template)

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al cargar el detalle: {}".format(str(error)))


@frappe.whitelist()
def download_files(doc_name, invoice_number):
    """Descarga (zip) los documentos adjuntos de una factura de collection
    (child docs_attach), igual que el flujo documenteme con sus adjuntos.
    """
    import zipfile
    from io import BytesIO

    try:
        docs = frappe.get_all(
            "qp_SP_PurchaseInvoiceDoc",
            filters={"parent": doc_name, "parenttype": "qp_SP_PurchaseInvoice"},
            fields=["file_name", "file_type", "file_id"],
        ) or []

        non_xml_files = [
            f for f in docs
            if (f.get("file_type") or "").upper() != "XML"
        ]

        if not non_xml_files:
            frappe.local.response.filename = "{}.txt".format(invoice_number)
            frappe.local.response.filecontent = (
                "No hay documentos disponibles para descargar."
            )
            frappe.local.response.type = "download"
            return

        zip_buffer = BytesIO()
        written = 0
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in non_xml_files:
                try:
                    if not f.get("file_id"):
                        continue
                    file_doc = frappe.get_doc("File", f.get("file_id"))
                    content = file_doc.get_content()
                    if not content:
                        continue
                    file_name = (f.get("file_name") or "documento").strip() or "documento"
                    zf.writestr(file_name, content)
                    written += 1
                except Exception:
                    continue

        if written == 0:
            frappe.local.response.filename = "{}.txt".format(invoice_number)
            frappe.local.response.filecontent = (
                "No hay documentos disponibles para descargar."
            )
            frappe.local.response.type = "download"
            return

        zip_buffer.seek(0)

        frappe.local.response.filename = "{}.zip".format(invoice_number)
        frappe.local.response.filecontent = zip_buffer.getvalue()
        frappe.local.response.type = "download"

    except Exception as error:
        frappe.local.response.filename = "error.txt"
        frappe.local.response.filecontent = (
            "Error al generar descarga: {}".format(str(error))
        )
        frappe.local.response.type = "download"


@frappe.whitelist()
def get_notifications(doc_name):
    """Notificaciones (alertas) de una factura de cuenta de cobro.

    Retorna {"alerts": [abiertas], "history": [todas desc]} desde
    qp_SP_PurchaseInvoiceNotification. Es la fuente del modal que abre el icono
    de alerta. Con data (facade) lee del store (memoria si simulacion); sin
    data usa frappe (real).
    """
    try:
        if not doc_name:
            response(400, "Falta el documento")
            return

        data = runtime.resolve().get("data")
        fields = [
            "name",
            "notification_date",
            "notification_type",
            "notification_message",
            "status",
        ]
        order_by = "notification_date desc"

        if data is not None:
            notifications = data.get_all(
                NOTIFICATIONS,
                filters={"parent": doc_name},
                fields=fields,
                order_by=order_by,
            )
        else:
            notifications = frappe.get_all(
                NOTIFICATIONS,
                filters={"parent": doc_name},
                fields=fields,
                order_by=order_by,
            )

        alerts = [
            n for n in notifications
            if n.get("status") == "Abierta"
        ]

        response(200, "ok", {"alerts": alerts, "history": notifications})

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al obtener notificaciones: {}".format(str(error)))