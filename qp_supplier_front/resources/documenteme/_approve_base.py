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

from qp_supplier_front.infrastructure.adapters.documenteme_http_adapter import (
    get_receipt_total as _adapter_get_receipt_total,
)
from qp_supplier_front.resources.documenteme._alerts import (
    insert_alert,
    resolve_open_alerts,
)
from qp_supplier_front.resources.documenteme import simulation
from qp_supplier_front.resources.documenteme.auto_reject import (
    resolve_rule as _resolve_rule,
)
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.services.role_resolver import get_active_role
from qp_supplier_front.uses_cases.documenteme.approve import (
    approve_documents,
    collect_registrable_violations,
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
            "nvfac_conv",
            "nvmon_codi",
            "nvfac_stot",
            "nvfac_viva",
            "nvpro_nomb",
        ],
    )


def get_lines(doc):
    """Resuelve las lineas que alimentan el payload BC para una factura.

    Retorna (lines, error):
    - lines: lista de dicts {item_code, qty, rate, idx, receiving_no, order_no}.
    - error: mensaje si la factura no puede generar lineas (vacio si ok).

    Fuente de lineas:
    - Si la OC tiene recepciones: se usan los Purchase Receipt Items, cuyo
      item_code ya es el codigo BC. Aplica a credito (obligatorio) y a contado
      con recepcion.
    - Si no hay recepciones (contado sin recibo, o credito aprobado por el
      usuario en modo forzado): se toman las lineas de la factura del
      proveedor (qp_SP_DetailLine) y se homologa el codigo del proveedor
      (nvpro_codi) al codigo BC (bc_item_code) via la tabla
      qp_SP_ItemHomologation. Si algun codigo no tiene homologacion la
      factura queda en error (se mantiene en "E" con alerta).
    """
    purchase_order = doc.get("nvfac_orde")
    receipt_lines = get_lines_from_receipts(purchase_order)

    if receipt_lines:
        return receipt_lines, ""

    return get_lines_from_invoice(doc)


def get_lines_from_receipts(purchase_order):
    """Lineas desde los Purchase Receipt Items de una OC (codigo ya BC)."""
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


def get_lines_from_invoice(doc):
    """Lineas de la factura del proveedor homologadas al codigo BC.

    Resuelve el proveedor por tax_id (nvpro_ndoc), carga el mapa de
    homologacion y las lineas de detalle de la factura. Si falta alguna
    homologacion retorna un error con los codigos pendientes.

    El JSON a BC lleva la informacion que la factura tiene: si el contado
    tiene OC (pero no recibo) se incluye NoPedido (order_no); sin OC/recibo
    van vacios y BC decide.
    """
    from qp_supplier_front.infrastructure.adapters.item_homologation_adapter import (
        get_homologation_map,
        get_invoice_detail_lines,
        resolve_supplier,
    )
    from qp_supplier_front.uses_cases.documenteme.approve import homologate_lines

    supplier = resolve_supplier(doc.get("nvpro_ndoc"))
    homologation_map = get_homologation_map(supplier)
    detail_lines = get_invoice_detail_lines(doc.get("name"))

    lines, missing_codes = homologate_lines(
        detail_lines,
        homologation_map,
        order_no=doc.get("nvfac_orde") or "",
    )

    if missing_codes:
        return [], (
            "Faltan homologaciones de producto: {}"
        ).format(", ".join(sorted(set(missing_codes))))

    if not lines:
        return [], "La factura no tiene lineas homologadas para enviar"

    return lines, ""


def po_exists(purchase_order):
    if not purchase_order:
        return False
    return bool(frappe.db.exists("Purchase Order", purchase_order))


def get_headquarter(purchase_order):
    if not purchase_order:
        return ""
    return frappe.db.get_value("Purchase Order", purchase_order, "qp_headquarter") or ""


def receipts_total(purchase_order):
    """Suma del total de Purchase Receipt por OC (delega en el adapter)."""
    return _adapter_get_receipt_total(purchase_order, frappe_module=frappe)


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


def mark_duplicate_registered(doc, error, now):
    """Marca una factura duplicada como creada en BC y detiene el reintento.

    Al recibir "Ya existe la factura de compra..." de BC, el codigo BC no es
    recuperable: se detiene el reintento de creacion, se fija la factura en
    "BCC" (Creada en BC) y se inserta una alerta indicando que falta el codigo
    BC, para gestion manual. No se crea la referencia (qp_SP_PurchaseInvoice /
    qp_SP_PurchaseInvoiceBC) porque un invoice_id falso romperia el enlace de
    la confirmacion externa.
    """
    frappe.db.set_value(
        "qp_SP_DocumentDetail",
        doc.get("name"),
        "nvfac_esta",
        "BCC",
    )
    doc["nvfac_esta"] = "BCC"
    resolve_open_alerts(doc.get("name"))
    insert_alert(
        doc.get("name"),
        (
            "La factura ya existe en BC; se detuvo el reintento. "
            "No se pudo obtener el codigo BC para enlazar su confirmacion. "
            "Error: {}".format(error)
        ),
        now,
    )


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
def approve_documents_core(doc_names, send_request_fn=None, force=False):
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
        get_headquarter_fn=get_headquarter,
        po_exists_fn=po_exists,
        receipts_total_fn=receipts_total,
        send_request_fn=send_request_fn or send_purchase_invoice_request,
        parse_doc_numbers_fn=parse_doc_numbers,
        persist_invoice_fn=persist_invoice,
        mark_registered_fn=mark_registered,
        mark_error_fn=mark_error,
        mark_duplicate_registered_fn=mark_duplicate_registered,
        commit_fn=frappe.db.commit,
        now=_make_now(),
        force=force,
        resolve_rule_fn=_resolve_rule,
    )


def collect_document_violations(doc_names):
    """Advertencias de aprobacion automatica por factura (pre-validacion).

    Sin efectos secundarios: solo lee los documentos y retorna
    [{"nvfac_nume", "violations": [...]}] para las facturas que no cumplen
    la regla OC - recepcion - montos pero aun pueden aprobarse de forma
    forzada por el usuario.
    """
    docs = get_docs(doc_names)
    return collect_registrable_violations(
        docs, po_exists, receipts_total, resolve_rule_fn=_resolve_rule
    )


def run_approve(doc_names_raw, send_request_fn=None, force=False):
    """Flujo manual: valida permisos y aprueba el lote seleccionado.

    Con force=True (el usuario confirmo las violaciones en el front) se
    omiten las advertencias de OC - recepcion - montos; los estados
    definitivos/en proceso siguen bloqueando.
    """
    doc_names = parse_json(doc_names_raw)

    if not _has_permission(frappe.get_roles()):
        response(403, "No tiene permisos para aprobar facturas")
        return

    result = approve_documents_core(
        doc_names, send_request_fn=send_request_fn, force=force
    )
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
        response(500, "Error al aprobar: {}".format(detail), result)
        return

    response(200, "Factura(s) aprobada(s) correctamente", result)
