# -*- coding: utf-8 -*-
"""
_collection_invoice_base.py (resources/collection_accounts)
===========================================================
Cablea el nucleo puro de facturas de cuentas de cobro con implementaciones
Frappe. Es el equivalente de _approve_base.py para el nuevo flujo y sirve a
los flujos manual (resources/collection_accounts/collection_invoices.py) y
al modo simulador (runtime.py).

Diferencias frente al flujo documenteme:
  - La factura a registrar es un qp_SP_PurchaseInvoice ya existente (creado
    al insertar la cuenta de cobro): persist_invoice hace UPDATE (nunca
    INSERT) y marca la cuenta de cobro como "Facturado".
  - NO se crea qp_SP_PurchaseInvoiceBC ni se encolan eventos a documenteme:
    la aprobacion acaba en "BCC" y el rechazo es sincrono ("R").
  - Una sola linea BC por factura: primer item de la OC por el monto a
    facturar.
"""

import frappe
from frappe import parse_json

from qp_supplier_front.resources.collection_accounts._notifications import (
    insert_notification,
    resolve_open_notifications,
)
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.services.role_resolver import get_active_role
from qp_supplier_front.uses_cases.collection_invoices import mapping
from qp_supplier_front.uses_cases.collection_invoices.approve import (
    approve_collection_invoices,
)

ALLOWED_ROLES = {"Administrador Documenteme", "Administrador Sede Documenteme"}

PURCHASE_INVOICE = "qp_SP_PurchaseInvoice"
COLLECTION_ACCOUNT = "qp_SP_CollectionAccounts"
NOTIFICATIONS = "qp_SP_PurchaseInvoiceNotification"
ASSIGNED_USERS_DOCTYPE = "qp_SP_PurchaseInvoiceAssignedUser"
PURCHASE_INVOICE_DOC = "qp_SP_PurchaseInvoiceDoc"
COMMENT_DOCTYPE = "qp_SP_PurchaseInvoiceComment"
COMMENT_READ_DOCTYPE = "qp_SP_PurchaseInvoiceCommentRead"

DEFINITIVE_VIEW_STATES = ("BCC", "PA", "PR", "A", "R")


def _has_permission(user_roles):
    active = get_active_role(user_roles)
    return active in ALLOWED_ROLES


def _make_now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# =========================================================================
# Callbacks de infraestructura (reales)
# =========================================================================
def get_docs(doc_names):
    """Lee los qp_SP_PurchaseInvoice y los convierte al dict documenteme."""
    rows = frappe.get_all(
        PURCHASE_INVOICE,
        filters={"name": ["in", list(doc_names)]},
        fields=[
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
        ],
    )
    return [mapping.build_document_dict(row) for row in rows]


def get_first_po_item(purchase_order):
    """Primer item de la orden de compra (codigo BC) o None."""
    if not purchase_order:
        return None
    items = frappe.db.sql(
        "SELECT item_code FROM `tabPurchase Order Item` "
        "WHERE parent = %s ORDER BY idx ASC, name ASC LIMIT 1",
        purchase_order,
    )
    if not items:
        return None
    return items[0][0]


def get_lines(doc):
    """Linea unica BC: primer item de la OC por el monto a facturar."""
    purchase_order = doc.get("nvfac_orde")
    if not purchase_order:
        return [], "La factura no tiene orden de compra"
    item_code = get_first_po_item(purchase_order)
    if not item_code:
        return [], "La orden de compra no tiene items"
    amount_payable = doc.get("nvfac_totp") or doc.get("nvfac_stot") or 0
    line = mapping.build_single_line(
        {"item_code": item_code},
        amount_payable,
        order_no=purchase_order,
    )
    return [line], ""


def po_exists(purchase_order):
    if not purchase_order:
        return False
    return bool(frappe.db.exists("Purchase Order", purchase_order))


def get_headquarter(purchase_order):
    if not purchase_order:
        return ""
    return frappe.db.get_value(
        "Purchase Order", purchase_order, "qp_headquarter"
    ) or ""


def receipt_bank(purchase_order):
    """Banco de recepciones (name, amount, date, qp_invoice) por OC."""
    from qp_supplier_front.infrastructure.adapters.documenteme_http_adapter import (
        get_receipt_bank as _adapter_get_receipt_bank,
    )
    return _adapter_get_receipt_bank(purchase_order, frappe_module=frappe)


def consume_receipts(doc, receipt_names):
    """Marca las recepciones asignadas con qp_invoice = nvfac_nume."""
    from qp_supplier_front.resources.documenteme._approve_base import (
        consume_receipts as _documenteme_consume_receipts,
    )
    return _documenteme_consume_receipts(doc, receipt_names)


def mark_collection_account_invoiced(doc):
    """Marca la cuenta de cobro origen como 'Facturado'."""
    account_name = doc.get("collection_account")
    if not account_name:
        return
    current = frappe.db.get_value(
        COLLECTION_ACCOUNT, account_name, "status"
    )
    if current != "Facturado":
        frappe.db.set_value(
            COLLECTION_ACCOUNT, account_name, "status", "Facturado"
        )


def persist_invoice(doc, doc_number, now):
    """Actualiza la fila existente del qp_SP_PurchaseInvoice y la cuenta
    de cobro. Nunca inserta (la factura ya existe desde la cuenta de cobro).
    """
    if not doc_number:
        doc_number = doc.get("nvfac_nume") or doc.get("name")
    frappe.db.set_value(
        PURCHASE_INVOICE,
        doc.get("name"),
        {
            "invoice_id": doc_number,
            "qp_status": "BCC",
            "qp_is_error": 0,
            "qp_error_message": "",
        },
    )
    resolve_open_notifications(doc.get("name"))
    mark_collection_account_invoiced(doc)
    return doc_number


def mark_registered(doc, doc_number):
    frappe.db.set_value(
        PURCHASE_INVOICE, doc.get("name"), "qp_status", "BCC"
    )
    resolve_open_notifications(doc.get("name"))


def mark_error(doc, error):
    frappe.db.set_value(
        PURCHASE_INVOICE,
        doc.get("name"),
        {
            "qp_is_error": 1,
            "qp_error_message": error,
        },
    )
    insert_notification(
        doc.get("name"),
        error,
        notification_type="ErrorUrgente",
    )


def mark_duplicate_registered(doc, error, now):
    """La factura ya existe en BC: el codigo BC no es recuperable. Se marca
    BCC sin invoice_id y la cuenta de cobro como facturada.
    """
    frappe.db.set_value(
        PURCHASE_INVOICE,
        doc.get("name"),
        {
            "qp_status": "BCC",
            "qp_is_error": 1,
            "qp_error_message": (
                "La factura ya existe en BC; falta el codigo BC. Error: {}"
            ).format(error),
        },
    )
    insert_notification(
        doc.get("name"),
        "La factura ya existe en BC; falta el codigo BC. Error: {}".format(error),
        now=now,
        notification_type="ErrorUrgente",
    )
    mark_collection_account_invoiced(doc)


def parse_doc_numbers(response):
    if not isinstance(response, dict):
        return []
    return response.get("invoices") or []


def attach_notification_info(rows, data=None):
    """Adjunta a cada fila de qp_SP_PurchaseInvoice la info de notificaciones
    (abiertas y urgentes) para pintar el icono de la columna.

    Con data (facade) lee del store (memoria si simulacion); sin data usa
    frappe (real).
    """
    names = [row.get("name") for row in (rows or []) if row.get("name")]
    if not names:
        return rows

    if data is not None:
        notifications = data.get_all(
            NOTIFICATIONS,
            filters={"parent": ["in", names]},
            fields=["parent", "notification_type", "status"],
        )
    else:
        notifications = frappe.get_all(
            NOTIFICATIONS,
            filters={"parent": ["in", names]},
            fields=["parent", "notification_type", "status"],
        )

    counts = {}
    for item in notifications or []:
        parent = item.get("parent")
        info = counts.setdefault(parent, {"open": 0, "urgent": 0, "count": 0})
        info["count"] += 1
        if item.get("status") == "Abierta":
            info["open"] += 1
            if item.get("notification_type") == "ErrorUrgente":
                info["urgent"] += 1

    for row in (rows or []):
        info = counts.get(row.get("name")) or {}
        row["notification_open"] = info.get("open", 0)
        row["notification_urgent"] = info.get("urgent", 0)
        row["notification_count"] = info.get("count", 0)

    return rows


def _resolve_references(data):
    """Adaptador de referencias de compras (real o memoria segun data)."""
    if data is not None:
        return data.references
    from qp_supplier_front.infrastructure.adapters.reference_source import (
        RealReferenceSource,
    )
    return RealReferenceSource()


def attach_reception_info(rows, data=None):
    """Enriquece cada fila de qp_SP_PurchaseInvoice para la lista (formato
    documenteme).

    - row["recepciones"]: recibos visibles de la OC (el banco de la factura)
      para la columna Recepcion.
    - row["productos_orden_compra"]: items de la OC (tabla 2 del detalle).
    - row["recepciones_detalle"]: banco visible de la OC agrupado por recibo
      (tabla 3 del detalle), con sus productos.
    - row["hide_unselected_recibos"]: True en estados definitivos (solo se
      muestran los reclamados por la factura).

    Con data (facade) lee del store (memoria si simulacion); sin data usa
    frappe (real).
    """
    from qp_supplier_front.services.enrich_document_detail import (
        build_po_products,
        build_receipt_products,
    )

    refs = _resolve_references(data)

    for row in (rows or []):
        purchase_order = row.get("purchase_order_id") or ""
        invoice_number = row.get("nvfac_nume") or ""
        definitive = row.get("qp_status") in DEFINITIVE_VIEW_STATES

        row["hide_unselected_recibos"] = definitive
        row["productos_orden_compra"] = (
            build_po_products(refs.po_items(purchase_order))
            if purchase_order
            else []
        )

        bank = []
        if purchase_order and invoice_number:
            bank = refs.bank_for_invoice(
                purchase_order, invoice_number
            ) or []
            if definitive:
                bank = [
                    item for item in bank if item.get("claimed_by_me")
                ]

        # Etiquetas por recibo (supplier_delivery_note o name) para badges y
        # detalle. Los badges muestran el banco de la OC (igual que el
        # detalle): antes de la aprobacion los recibos no estan reclamados
        # (qp_invoice vacio) y con la regla de "solo asignados" el badge
        # quedaria en blanco, a diferencia de documenteme.
        labels = {}
        if purchase_order:
            labels = {
                receipt.get("name"):
                    receipt.get("supplier_delivery_note") or receipt.get("name")
                for receipt in (refs.receipts_for(purchase_order) or [])
            }
        row["recepciones"] = [
            labels.get(item.get("name")) or item.get("name")
            for item in bank
        ]

        names = [item.get("name") for item in bank if item.get("name")]
        items = refs.receipt_items_for(names) if names else []
        products = build_receipt_products(items)

        products_by_receipt = {}
        for item, product in zip(items, products):
            products_by_receipt.setdefault(item.get("parent"), []).append(product)

        row["recepciones_detalle"] = [
            {
                "name": item.get("name"),
                "etiqueta": labels.get(item.get("name")) or item.get("name"),
                "fecha": item.get("date"),
                "monto": item.get("amount") or 0,
                "claimed_by_me": item.get("claimed_by_me"),
                "selectable": item.get("selectable", False),
                "productos": products_by_receipt.get(item.get("name"), []),
            }
            for item in bank
        ]

    return rows


def attach_assignment_info(rows, data=None):
    """Adjunta a cada fila de qp_SP_PurchaseInvoice los usuarios asignados
    (child assigned_users) con su nombre completo.

    - row["assigned_to_names"]: lista de nombres de los asignados.
    - row["assigned_to_name"]: texto multilinea "Asignado a:\n- name..." o None.

    Con data (facade) lee del store (memoria si simulacion); sin data usa
    frappe (real).
    """
    names = [row.get("name") for row in (rows or []) if row.get("name")]
    if not names:
        return rows

    if data is not None:
        children = data.get_all(
            ASSIGNED_USERS_DOCTYPE,
            filters={"parent": ["in", names], "parenttype": PURCHASE_INVOICE},
            fields=["parent", "user"],
        )
    else:
        children = frappe.get_all(
            ASSIGNED_USERS_DOCTYPE,
            filters={"parent": ["in", names], "parenttype": PURCHASE_INVOICE},
            fields=["parent", "user"],
        )

    user_ids = sorted({
        item.get("user") for item in children if item.get("user")
    })
    full_names = {}
    if user_ids:
        if data is not None:
            users = data.get_all(
                "User",
                filters={"name": ["in", user_ids]},
                fields=["name", "full_name"],
            )
        else:
            users = frappe.get_all(
                "User",
                filters={"name": ["in", user_ids]},
                fields=["name", "full_name"],
            )
        full_names = {
            user.get("name"): user.get("full_name") or user.get("name")
            for user in (users or [])
        }

    by_parent = {}
    for item in children or []:
        by_parent.setdefault(item.get("parent"), []).append(item.get("user"))

    for row in (rows or []):
        user_ids_row = by_parent.get(row.get("name")) or []
        names_row = [
            full_names.get(user_id) or user_id
            for user_id in user_ids_row
        ]
        row["assigned_to_names"] = names_row
        row["assigned_to_name"] = (
            "Asignado a:\n" + "\n".join("- " + name for name in names_row)
            if names_row
            else None
        )

    return rows


def _guess_doc_type(file_name):
    """Tipo de archivo derivado de la extension (p. ej. 'pdf' -> 'PDF')."""
    parts = (file_name or "").rsplit(".", 1)
    if len(parts) == 2 and parts[1].strip():
        return parts[1].strip().upper()
    return ""


def _account_docs_by_name(account_names, data=None):
    """Docs (Attach URL) de las cuentas de cobro, agrupados por cuenta."""
    account_names = [
        name for name in (account_names or []) if name
    ]
    if not account_names:
        return {}

    if data is not None:
        accounts = data.get_all(
            COLLECTION_ACCOUNT,
            filters={"name": ["in", account_names]},
            fields=["name", "docs"],
        )
    else:
        accounts = frappe.get_all(
            COLLECTION_ACCOUNT,
            filters={"name": ["in", account_names]},
            fields=["name", "docs"],
        )

    return {
        account.get("name"): (account.get("docs") or "").strip()
        for account in (accounts or [])
        if (account.get("docs") or "").strip()
    }


def attach_document_info(rows, data=None):
    """Adjunta a cada fila de qp_SP_PurchaseInvoice el resumen de sus
    documentos adjuntos (child docs_attach).

    - row["doc_count"]: cantidad de archivos adjuntos de la factura.
    - row["non_xml_count"]: cantidad de archivos no-XML (para el icono de
      descarga).

    Cuando la factura no tiene adjuntos no-XML en el child, se cae al
    documento de la cuenta de cobro (docs de qp_SP_CollectionAccounts), de
    modo que el icono de descarga se pinta aunque el docs_attach no se haya
    propagado (p. ej. facturas creadas antes de ese feature).

    Con data (facade) lee del store (memoria si simulacion); sin data usa
    frappe (real).
    """
    names = [row.get("name") for row in (rows or []) if row.get("name")]
    if not names:
        return rows

    if data is not None:
        docs = data.get_all(
            PURCHASE_INVOICE_DOC,
            filters={
                "parent": ["in", names],
                "parenttype": PURCHASE_INVOICE,
            },
            fields=["parent", "file_type"],
        )
    else:
        docs = frappe.get_all(
            PURCHASE_INVOICE_DOC,
            filters={
                "parent": ["in", names],
                "parenttype": PURCHASE_INVOICE,
            },
            fields=["parent", "file_type"],
        )

    docs_by_parent = {}
    for doc in docs or []:
        docs_by_parent.setdefault(doc.get("parent"), []).append(doc)

    account_docs_by_name = _account_docs_by_name(
        [row.get("collection_account") for row in (rows or [])],
        data=data,
    )

    for row in (rows or []):
        row_docs = docs_by_parent.get(row.get("name")) or []
        has_non_xml = any(
            (doc.get("file_type") or "").upper() != "XML"
            for doc in row_docs
        )

        # Fallback al documento de la cuenta de cobro cuando la factura no
        # tiene adjuntos no-XML (icono de descarga verde/downloadable).
        if not has_non_xml:
            account_docs = account_docs_by_name.get(
                row.get("collection_account")
            )
            if account_docs and _guess_doc_type(account_docs).upper() != "XML":
                row_docs = list(row_docs) + [{
                    "file_url": account_docs,
                    "file_type": _guess_doc_type(account_docs),
                }]
                docs_by_parent[row.get("name")] = row_docs

        row["doc_count"] = len(row_docs)
        row["non_xml_count"] = len([
            doc for doc in row_docs
            if (doc.get("file_type") or "").upper() != "XML"
        ])

    return rows


def _comment_session_user(data):
    """Usuario activo (real: sesion; memoria: Administrator)."""
    if data is not None:
        return "Administrator"
    return getattr(frappe.session, "user", "Administrator")


def _comment_own_name(data, user):
    """Nombre visible del usuario (real: fullname; memoria: Administrator)."""
    if data is not None:
        return "Administrator"
    try:
        return frappe.utils.get_fullname(user) or user
    except Exception:
        return user


def attach_comment_info(rows, data=None):
    """Adjunta a cada fila de qp_SP_PurchaseInvoice el resumen de su
    conversacion (child comments + comment_read).

    - row["comment_count"]: cantidad de comentarios de la factura.
    - row["has_unread_comment"]: True si el usuario actual tiene comentarios
      ajenos posteriores a su ultima lectura.

    Con data (facade) lee del store (memoria si simulacion); sin data usa
    frappe (real).
    """
    names = [row.get("name") for row in (rows or []) if row.get("name")]
    if not names:
        return rows

    user = _comment_session_user(data)
    own = _comment_own_name(data, user)

    if data is not None:
        comments = data.get_all(
            COMMENT_DOCTYPE,
            filters={"parent": ["in", names]},
            fields=["parent", "entry_by", "entry_date"],
        )
        reads = data.get_all(
            COMMENT_READ_DOCTYPE,
            filters={"parent": ["in", names], "user": user},
            fields=["parent", "last_read"],
        )
    else:
        comments = frappe.get_all(
            COMMENT_DOCTYPE,
            filters={"parent": ["in", names]},
            fields=["parent", "entry_by", "entry_date"],
        )
        reads = frappe.get_all(
            COMMENT_READ_DOCTYPE,
            filters={"parent": ["in", names], "user": user},
            fields=["parent", "last_read"],
        )

    comments_by_parent = {}
    for comment in comments or []:
        comments_by_parent.setdefault(comment.get("parent"), []).append(comment)

    last_read_by_parent = {
        read.get("parent"): read.get("last_read")
        for read in reads or []
    }

    for row in (rows or []):
        doc_comments = comments_by_parent.get(row.get("name")) or []
        last_read = last_read_by_parent.get(row.get("name"))
        row["comment_count"] = len(doc_comments)
        row["has_unread_comment"] = any(
            (comment.get("entry_by") or "") != own
            and str(comment.get("entry_date") or "")
            and not (last_read and str(comment.get("entry_date")) <= str(last_read))
            for comment in doc_comments
        )

    return rows


def send_purchase_invoice_request(endpoint_code, payload):
    """Envia el payload a BC (middleware) y registra el request log."""
    from qp_supplier_front.resources.documenteme._approve_base import (
        send_purchase_invoice_request as _documenteme_send,
    )
    return _documenteme_send(endpoint_code, payload)


# =========================================================================
# Orquestacion compartida
# =========================================================================
def collect_document_violations(doc_names):
    """Violaciones de aprobacion automatica por factura (sin side effects)."""
    docs = get_docs(doc_names)
    return mapping.collect_validation_violations(
        docs, po_exists, receipt_bank, resolve_rule_fn=resolve_rule
    )


def approve_collection_invoices_core(doc_names, send_request_fn=None,
                                     force=False):
    from qp_supplier_front.resources.collection_accounts import runtime

    components = runtime.resolve()
    if send_request_fn is None:
        send_request_fn = components.get("send_request_fn") \
            or send_purchase_invoice_request

    cb = components.get("approve_callbacks") or {}

    result = approve_collection_invoices(
        doc_names,
        get_docs_fn=cb.get("get_docs_fn", get_docs),
        get_lines_fn=cb.get("get_lines_fn", get_lines),
        get_headquarter_fn=cb.get("get_headquarter_fn", get_headquarter),
        po_exists_fn=cb.get("po_exists_fn", po_exists),
        receipt_bank_fn=cb.get("receipt_bank_fn", receipt_bank),
        send_request_fn=send_request_fn,
        parse_doc_numbers_fn=cb.get("parse_doc_numbers_fn", parse_doc_numbers),
        persist_invoice_fn=cb.get("persist_invoice_fn", persist_invoice),
        mark_registered_fn=cb.get("mark_registered_fn", mark_registered),
        mark_error_fn=cb.get("mark_error_fn", mark_error),
        mark_duplicate_registered_fn=cb.get(
            "mark_duplicate_registered_fn", mark_duplicate_registered
        ),
        consume_receipts_fn=cb.get("consume_receipts_fn", consume_receipts),
        commit_fn=frappe.db.commit,
        now=_make_now(),
        force=force,
        resolve_rule_fn=cb.get("resolve_rule_fn", resolve_rule),
    )
    return result


def reject(doc_names, motive, is_invoice_error=False):
    """Rechazo manual SINCRONO: solo cambia el estado local a 'R'."""
    for name in doc_names:
        frappe.db.set_value(
            PURCHASE_INVOICE,
            name,
            {
                "qp_status": "R",
                "qp_motive": motive or "",
                "qp_reject_is_invoice_error": 1 if is_invoice_error else 0,
            },
        )
        resolve_open_notifications(name)
        insert_notification(
            name,
            "Factura rechazada: {}".format(motive or "Sin motivo"),
            notification_type="Alerta",
        )
    frappe.db.commit()


def set_confirmation(invoice_id, confirmation_id):
    """Confirma la factura en BC (sin eventos): BCC -> A."""
    if not invoice_id or not confirmation_id:
        return {"ok": False, "error": "invoice_id y confirmation_id son requeridos"}
    rows = frappe.get_all(
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
    frappe.db.set_value(
        PURCHASE_INVOICE,
        rows[0]["name"],
        {
            "confirmation_id": confirmation_id,
            "qp_status": "A",
        },
    )
    resolve_open_notifications(rows[0]["name"])
    frappe.db.commit()
    return {"ok": True}


def parse_json_arg(value):
    if value in (None, ""):
        return None
    return parse_json(value)


def resolve_rule(doc, master_setup=None):
    """Regla de rechazo activa (Supplier.auto_reject con fallback MasterSetup).

    Delega en el adaptador documenteme: las facturas de cuentas de cobro
    (CONTADO) respetan la misma regla que el contado de documenteme.
    """
    from qp_supplier_front.resources.documenteme.auto_reject import (
        resolve_rule as _documenteme_resolve_rule,
    )
    return _documenteme_resolve_rule(doc, master_setup=master_setup)