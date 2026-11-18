# -*- coding: utf-8 -*-
"""
purchase_order_reference.py (documenteme) — infraestructura
==========================================================
Asignacion manual de la(s) OC de una factura de credito que llego sin orden.

Flujo:
- get_purchase_order_candidates: OC del proveedor de la factura, con su tipo,
  sede y estado de recepciones, para que el usuario elija una o varias.
- assign_purchase_order: valida y persiste la OC manual (se refleja en
  nvfac_orde), reasigna al grupo (oc_type, headquarter) de la OC y dispara el
  pipeline normal (asignar, aprobar, rechazar). El boton "Solo asignar"
  ejecuta el pipeline automatico; "Asignar y Aprobar" ademas aprueba en el
  acto, igual que la referencia de una nota credito.

Reutiliza: parse_purchase_orders, po_supplier_match, get_oc_context, el banco
de recepciones y el patron de nc_reference.py.
"""

import frappe
from frappe import parse_json

from qp_supplier_front.resources.documenteme._approve_base import (
    _has_permission,
    approve_documents_core,
    get_supplier_by_tax_id,
    is_service_supplier_doc,
    make_delivery_order_predicate,
    po_supplier_match,
)
from qp_supplier_front.resources.documenteme.approve import resolve_backend
from qp_supplier_front.resources.documenteme.auto_approve import (
    run_auto_approve,
)
from qp_supplier_front.resources.documenteme.auto_assign import (
    get_oc_context,
    get_receipt_bank,
    reassign_to_oc_group,
    run_auto_assign,
)
from qp_supplier_front.resources.documenteme.auto_reject import (
    po_exists,
    run_auto_reject,
)
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.uses_cases.documenteme.conversion import (
    is_cash_invoice,
    is_credit_note,
)
from qp_supplier_front.uses_cases.documenteme.no_purchase_order import (
    has_purchase_orders,
)
from qp_supplier_front.uses_cases.documenteme.purchase_orders import (
    parse_purchase_orders,
)

ASSIGNABLE_STATES = ("E", "SO")


def _is_true(value):
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in ("true", "1", "yes", "si")


def _parse_orders(value):
    """Acepta lista, JSON array o string separado por comas."""
    if isinstance(value, (list, tuple)):
        return parse_purchase_orders(value)
    text = str(value or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            return parse_purchase_orders(parse_json(text))
        except Exception:
            return []
    return parse_purchase_orders(text)


def _get_doc(doc_name):
    return frappe.get_doc("qp_SP_DocumentDetail", doc_name)


def _validate_scope(doc):
    """Devuelve un mensaje de error o vacio si la factura es asignable."""
    if is_credit_note(doc.get("nvtip_docu")):
        return "Las notas de credito usan la referencia de factura"
    if is_cash_invoice(doc.get("nvfac_conv")):
        return "Solo aplica a facturas de credito"
    if is_service_supplier_doc(doc):
        return "Un proveedor de servicio no requiere orden de compra"
    if make_delivery_order_predicate()(doc):
        return "Una factura de delivery no requiere orden de compra"
    if doc.get("nvfac_esta") not in ASSIGNABLE_STATES:
        return "La factura no esta pendiente de orden de compra"
    if has_purchase_orders(doc) and not doc.get("qp_manual_purchase_order"):
        return "La factura ya tiene una orden de compra del origen"
    return ""


def _receipt_summary(purchase_order):
    bank = get_receipt_bank(purchase_order) or []
    unclaimed = [row for row in bank if not row.get("qp_invoice")]
    total = sum(float(row.get("amount") or 0) for row in bank)
    unclaimed_total = sum(float(row.get("amount") or 0) for row in unclaimed)
    return {
        "has_receipts": bool(bank),
        "receipt_count": len(bank),
        "receipt_total": total,
        "unclaimed_count": len(unclaimed),
        "unclaimed_total": unclaimed_total,
    }


def _order_row(purchase_order):
    summary = _receipt_summary(purchase_order.get("name"))
    return {
        "name": purchase_order.get("name"),
        "supplier": purchase_order.get("supplier"),
        "transaction_date": str(purchase_order.get("transaction_date") or ""),
        "grand_total": purchase_order.get("grand_total"),
        "oc_type": purchase_order.get("qp_oc_type"),
        "headquarter": purchase_order.get("qp_headquarter"),
        "status": purchase_order.get("status"),
    }, summary


@frappe.whitelist()
def get_purchase_order_candidates(doc_name, search=None, start=None, end=None,
                                  limit=50):
    """OC candidatas del proveedor de la factura, con sus recepciones."""
    try:
        if not _has_permission(frappe.get_roles()):
            response(403, "No tiene permisos para asignar la orden de compra")
            return

        doc = _get_doc(doc_name)
        error = _validate_scope(doc)
        if error:
            response(400, error)
            return

        supplier = get_supplier_by_tax_id(doc.get("nvpro_ndoc"))
        if not supplier:
            response(200, "ok", {"orders": []})
            return

        # El flujo normal (get_oc_context) acepta la OC por nombre aunque siga
        # en borrador: las POs sincronizadas desde BC llegan sin submitir.
        # Solo se excluyen las canceladas.
        filters = {"supplier": supplier, "docstatus": ["<", 2]}
        if start:
            filters["transaction_date"] = [">=", str(start)]
        if end:
            if "transaction_date" in filters:
                filters["transaction_date"] = ["between", [str(start), str(end)]]
            else:
                filters["transaction_date"] = ["<=", str(end)]
        if search:
            filters["name"] = ["like", "%{0}%".format(str(search).strip())]

        rows = frappe.get_all(
            "Purchase Order",
            filters=filters,
            fields=[
                "name",
                "supplier",
                "transaction_date",
                "grand_total",
                "qp_oc_type",
                "qp_headquarter",
                "qp_order_confirmation_no",
                "status",
            ],
            order_by="transaction_date desc, name desc",
            limit=int(limit or 50),
        )

        orders = []
        for row in (rows or []):
            # El flujo normal solo reconoce la OC cuando su nombre es el
            # order_confirmation_no (get_oc_context).
            if (row.get("qp_order_confirmation_no") or "") != row.get("name"):
                continue
            if (row.get("status") or "") == "Cancelled":
                continue
            order, summary = _order_row(row)
            order.update(summary)
            orders.append(order)

        response(200, "ok", {"orders": orders})

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al obtener ordenes de compra: {}".format(
            str(error)))


@frappe.whitelist()
def assign_purchase_order(doc_name, purchase_orders, approve="false"):
    """Asigna una o varias OC y dispara el flujo normal de la factura."""
    try:
        if not _has_permission(frappe.get_roles()):
            response(403, "No tiene permisos para asignar la orden de compra")
            return

        orders = _parse_orders(purchase_orders)
        if not orders:
            response(400, "Debe seleccionar al menos una orden de compra")
            return

        doc = _get_doc(doc_name)
        error = _validate_scope(doc)
        if error:
            response(400, error)
            return

        for order in orders:
            if not po_exists(order):
                response(400, "La orden de compra {} no existe".format(order))
                return
            probe = {
                "nvfac_orde": order,
                "nvpro_ndoc": doc.get("nvpro_ndoc"),
            }
            if not po_supplier_match(probe):
                response(
                    400,
                    "La orden de compra {} no pertenece al proveedor".format(
                        order),
                )
                return
            if get_oc_context(order) is None:
                response(
                    400,
                    "La orden de compra {} no es valida para el flujo".format(
                        order),
                )
                return

        value = ", ".join(orders)
        user = frappe.session.user
        frappe.db.set_value("qp_SP_DocumentDetail", doc_name, {
            "qp_manual_purchase_order": value,
            "nvfac_orde": value,
            "qp_manual_po_assigned_by": user,
            "qp_manual_po_assigned_at": frappe.utils.now(),
            "nvfac_esta": "E",
        })

        from qp_supplier_front.infrastructure.adapters.timeline_adapter import (
            RealTimelineAdapter,
        )
        from qp_supplier_front.resources.documenteme._alerts import insert_alert

        timeline = RealTimelineAdapter(frappe_module=frappe)
        timeline.set_state(doc_name, "E")

        reassign = reassign_to_oc_group(doc_name)
        insert_alert(doc_name, _build_message(orders, user, reassign),
                     frappe.utils.now())

        run_auto_assign(doc_names=[doc_name])

        payload = {
            "orders": orders,
            "reassign": reassign,
        }

        if not _is_true(approve):
            payload["result"] = run_auto_approve(
                enqueue=True, doc_names=[doc_name])
            run_auto_reject(enqueue=True, doc_names=[doc_name])
            frappe.db.commit()
            response(200, "Orden de compra asignada", payload)
            return

        # La OC ya quedo persistida y reasignada: se confirma antes de
        # aprobar para no perderla si la aprobacion requiere accion manual.
        frappe.db.commit()
        result = approve_documents_core(
            [doc_name], backend=resolve_backend())
        frappe.db.commit()
        payload["result"] = result

        errors = (result or {}).get("errors") or []
        if errors:
            detail = ", ".join(
                "{}: {}".format(err.get("nvfac_nume"), err.get("error"))
                for err in errors
            )
            response(500, "OC asignada; error al aprobar: {}".format(detail),
                     payload)
            return

        response(200, "Orden de compra asignada", payload)

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al asignar la orden de compra: {}".format(
            str(error)))


def _build_message(orders, user, reassign):
    message = "OC asignada manualmente: {0} por {1}.".format(
        ", ".join(orders), user)
    if not reassign.get("reassigned"):
        return message + (
            " No se encontro grupo para la OC; se conservan los asignados "
            "actuales.")
    previous = ", ".join(reassign.get("previous") or []) or "-"
    current = ", ".join(reassign.get("users") or []) or "-"
    return message + " Reasignado de: {0} a: {1}.".format(previous, current)
