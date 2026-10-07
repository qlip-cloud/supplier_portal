# -*- coding: utf-8 -*-
"""
nc_reference.py (documenteme) — infraestructura
==============================================
Asignacion manual de la factura de compra de referencia de una nota de
credito tipo 5 (devolucion GP).

Cuando el proveedor no puede agregar la referencia en el XML (la factura
referenciada ya fue aceptada), la NC llega sin referencia y con un rango de
fechas (cbc:StartDate/cbc:EndDate) almacenado en qp_ref_date_start/end. Estas
funciones whitelist:

- get_reference_candidates: rango del XML + facturas candidatas del proveedor
  (gp_tipo_factura_doc 1/2) dentro del rango.
- assign_reference: asigna la PI seleccionada (qp_ref_invoice = nvfac_nume) y
  opcionalmente dispara la aprobacion de inmediato.

Las NC tipo 4 (proveedor de servicio) nunca requieren referencia.
"""

import frappe
from frappe import parse_json

from qp_supplier_front.resources.documenteme._approve_base import (
    _has_permission,
    get_supplier_by_tax_id,
    is_service_supplier_doc,
)
from qp_supplier_front.resources.response import handler as response


def _get_period_from_files(doc_name):
    """Rango (start, end) desde el XML adjunto (fallback si campos vacios)."""
    import base64

    from qp_supplier_front.services.xml_period import extract_period_dates

    attach_rows = frappe.get_all(
        "qp_SP_DocumentAttach",
        filters={"parent": doc_name, "parenttype": "qp_SP_DocumentDetail"},
        fields=["file_id", "file_type"],
    )
    for row in attach_rows or []:
        if (row.get("file_type") or "").upper() != "XML":
            continue
        file_id = row.get("file_id")
        if not file_id:
            continue
        try:
            file_doc = frappe.get_doc("File", file_id)
            content = file_doc.get_content()
        except Exception:
            continue
        if not content:
            continue
        start, end = extract_period_dates(content)
        if start or end:
            return start, end
    return None, None


def _nc_period(doc):
    """Rango de fechas de la NC (campos o XML adjunto)."""
    start = (doc or {}).get("qp_ref_date_start")
    end = (doc or {}).get("qp_ref_date_end")
    if start or end:
        return start, end
    return _get_period_from_files((doc or {}).get("name"))


def _resolve_reference_pi(doc_name, invoice_number):
    """Valida que la PI exista, sea del proveedor y tipo 1/2.

    Retorna la fila de qp_SP_PurchaseInvoice o None.
    """
    from qp_supplier_front.resources.documenteme._approve_base import (
        get_referenced_pi,
    )

    if not invoice_number:
        return None
    pi = get_referenced_pi(str(invoice_number))
    if not pi:
        return None
    try:
        gp_tipo = int(pi.get("gp_tipo_factura_doc") or 0)
    except (TypeError, ValueError):
        gp_tipo = 0
    if gp_tipo not in (1, 2):
        return None
    return pi


@frappe.whitelist()
def get_reference_candidates(doc_name, start=None, end=None):
    """Candidatas de referencia para una NC tipo 5.

    Retorna {"start", "end", "invoices"}: rango de fechas efectivo y las
    facturas de compra (gp_tipo_factura_doc 1/2) del proveedor cuya fecha de
    registro (registration_date) cae dentro del rango.

    El rango lo elige el usuario en el front (dos datepickers): si envia
    ``start``/``end`` se usan tal cual; si faltan se completan con el rango del
    XML (qp_ref_date_start/end o parseo del adjunto). Asi una NC cuyo XML no
    trae periodo puede filtrar las candidatas igual.
    """
    try:
        if not _has_permission(frappe.get_roles()):
            response(403, "No tiene permisos para asignar la referencia")
            return

        doc = frappe.get_doc("qp_SP_DocumentDetail", doc_name)
        if (doc.get("nvtip_docu") or "") != "C":
            response(400, "El documento no es una nota de credito")
            return
        if is_service_supplier_doc(doc):
            response(400, "Las notas de credito de servicio no requieren referencia")
            return

        start = str(start or "").strip()
        end = str(end or "").strip()
        if not start or not end:
            default_start, default_end = _nc_period(doc)
            start = start or default_start or ""
            end = end or default_end or ""
        if not start or not end:
            response(200, "ok", {"start": start, "end": end, "invoices": []})
            return

        supplier = get_supplier_by_tax_id(doc.get("nvpro_ndoc"))
        invoices = []
        if supplier:
            invoices = frappe.get_all(
                "qp_SP_PurchaseInvoice",
                filters={
                    "supplier": supplier,
                    "gp_tipo_factura_doc": ["in", ["1", "2"]],
                    "registration_date": ["between", [start, end]],
                },
                fields=[
                    "name", "invoice_id", "nvfac_nume", "detail",
                    "registration_date", "subtotal", "status",
                ],
                order_by="registration_date desc",
            )
            # El valor a guardar como referencia es el numero de factura del
            # proveedor (nvfac_nume o detail); invoice_id es el numero interno.
            for row in invoices:
                row["referencia"] = (
                    row.get("nvfac_nume") or row.get("detail")
                    or row.get("name") or ""
                )

            # Estado documenteme de la factura referenciada: el nombre de la PI
            # coincide con el documento documenteme que la origino.
            pis_by_name = {row.get("name"): row for row in invoices}
            if pis_by_name:
                est_rows = frappe.get_all(
                    "qp_SP_DocumentDetail",
                    filters={"name": ["in", list(pis_by_name)]},
                    fields=["name", "nvfac_esta"],
                )
            else:
                est_rows = []
            est_by_name = {r.get("name"): (r.get("nvfac_esta") or "")
                           for r in (est_rows or [])}
            for row in invoices:
                row["nvfac_esta"] = est_by_name.get(row.get("name")) or ""

        response(200, "ok", {"start": start, "end": end, "invoices": invoices})

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al obtener candidatas de referencia: {}".format(str(error)))


@frappe.whitelist()
def assign_reference(doc_name, invoice_number, approve="false"):
    """Asigna la factura de compra de referencia a una NC tipo 5.

    - approve=false ("Solo asignar"): persiste qp_ref_invoice y pasa a "V"
      (Lista para Registro); la aprobacion la hara el flujo automatico.
    - approve=true ("Asignar y Aprobar"): ademas dispara la aprobacion de la
      NC con el pipeline actual (create en GP/BC -> BCC -> confirmacion).
    """
    try:
        if not _has_permission(frappe.get_roles()):
            response(403, "No tiene permisos para asignar la referencia")
            return

        do_approve = bool(parse_json(approve)) if approve else False
        invoice_number = str(invoice_number or "")

        doc = frappe.get_doc("qp_SP_DocumentDetail", doc_name)
        if (doc.get("nvtip_docu") or "") != "C":
            response(400, "El documento no es una nota de credito")
            return
        if is_service_supplier_doc(doc):
            response(400, "Las notas de credito de servicio no requieren referencia")
            return

        pi = _resolve_reference_pi(doc_name, invoice_number)
        if not pi:
            response(400, "La factura de compra seleccionada no es una referencia valida")
            return

        frappe.db.set_value("qp_SP_DocumentDetail", doc_name, "qp_ref_invoice", invoice_number)
        frappe.db.set_value("qp_SP_DocumentDetail", doc_name, "nvfac_esta", "V")

        from qp_supplier_front.infrastructure.adapters.timeline_adapter import (
            RealTimelineAdapter,
        )
        RealTimelineAdapter(frappe_module=frappe).set_state(doc_name, "V")

        if not do_approve:
            frappe.db.commit()
            response(200, "Referencia asignada; la factura queda lista para aprobacion", {
                "nvfac_esta": "V",
            })
            return

        from qp_supplier_front.resources.documenteme._approve_base import (
            approve_documents_core,
        )
        from qp_supplier_front.resources.documenteme.approve import (
            resolve_backend,
        )

        result = approve_documents_core([doc_name], backend=resolve_backend())
        frappe.db.commit()

        errors = result.get("errors") or []
        if errors:
            detail = ", ".join(
                "{}: {}".format(err.get("nvfac_nume"), err.get("error"))
                for err in errors
            )
            response(500, "Error al aprobar: {}".format(detail), result)
            return

        response(200, "Referencia asignada y nota de credito aprobada", result)

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al asignar la referencia: {}".format(str(error)))