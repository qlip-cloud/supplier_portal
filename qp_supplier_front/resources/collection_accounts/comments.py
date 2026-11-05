# -*- coding: utf-8 -*-
"""
comments.py (resources/collection_accounts)
===========================================
Servicios de conversacion (comentarios) de las facturas de cuentas de cobro
(qp_SP_PurchaseInvoice). Replica el flujo documenteme (timeline/comentarios) de
forma aislada: comentarios + marcas de lectura por usuario (para el icono de
no-leidos).

Endpoints:
  - get_conversation(doc_name) -> {comments, unread_count, has_unread}
  - add_comment(doc_name, comment) -> lista actualizada de comentarios
  - mark_conversation_read(doc_name) -> {unread_count, has_unread}

Dual real/memoria via runtime.resolve().get("data"): con facade (data) se lee y
escribe en el MemoryStore de la sesion (MemDoc), sin data se usa frappe.
"""

import frappe

from qp_supplier_front.resources.collection_accounts import runtime
from qp_supplier_front.resources.response import handler as response

PURCHASE_INVOICE = "qp_SP_PurchaseInvoice"
COMMENT_DOCTYPE = "qp_SP_PurchaseInvoiceComment"
COMMENT_READ_DOCTYPE = "qp_SP_PurchaseInvoiceCommentRead"


def _now_str():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _current_user(data):
    """Usuario activo (real: sesion; memoria: Administrator)."""
    if data is not None:
        return "Administrator"
    return getattr(frappe.session, "user", "Administrator")


def _own_name(data, user):
    """Nombre visible del usuario (real: fullname; memoria: Administrator)."""
    if data is not None:
        return "Administrator"
    try:
        return frappe.utils.get_fullname(user) or user
    except Exception:
        return user


def _read_comments(data, doc_name):
    """Comentarios de la factura, ordenados desc por entry_date."""
    fields = ["message", "entry_by", "entry_date"]
    if data is not None:
        rows = data.get_all(
            COMMENT_DOCTYPE,
            filters={"parent": doc_name},
            fields=fields,
            order_by="entry_date desc",
        )
    else:
        rows = frappe.get_all(
            COMMENT_DOCTYPE,
            filters={"parent": doc_name},
            fields=fields,
            order_by="entry_date desc",
        )
    return [
        {
            "message": row.get("message") or "",
            "entry_by": row.get("entry_by") or "",
            "entry_date": row.get("entry_date") or "",
        }
        for row in (rows or [])
    ]


def _last_read_for(data, doc_name, user):
    if data is not None:
        rows = data.get_all(
            COMMENT_READ_DOCTYPE,
            filters={"parent": doc_name, "user": user},
            fields=["last_read"],
        )
    else:
        rows = frappe.get_all(
            COMMENT_READ_DOCTYPE,
            filters={"parent": doc_name, "user": user},
            fields=["last_read"],
        )
    return rows[0].get("last_read") if rows else None


def _unread_count(data, doc_name, user):
    """Comentarios ajenos con entry_date posterior al last_read del usuario."""
    last_read = _last_read_for(data, doc_name, user)
    own = _own_name(data, user)

    if data is not None:
        comments = data.get_all(
            COMMENT_DOCTYPE,
            filters={"parent": doc_name},
            fields=["entry_by", "entry_date"],
        )
    else:
        comments = frappe.get_all(
            COMMENT_DOCTYPE,
            filters={"parent": doc_name},
            fields=["entry_by", "entry_date"],
        )

    count = 0
    for comment in comments or []:
        if (comment.get("entry_by") or "") == own:
            continue
        entry_date = str(comment.get("entry_date") or "")
        if last_read and entry_date and entry_date <= str(last_read):
            continue
        count += 1
    return count


def _insert_comment_row(doc_name, row):
    """Inserta un comentario como child directo (sin re-save del padre):
    evita revalidar links del qp_SP_PurchaseInvoice y re-disparar hooks."""
    now = row.get("entry_date") or _now_str()
    try:
        last = frappe.db.sql(
            """
            SELECT COALESCE(MAX(idx), 0)
            FROM `tabqp_SP_PurchaseInvoiceComment`
            WHERE parent = %s AND parenttype = %s
            """,
            (doc_name, PURCHASE_INVOICE),
        ) or [[0]]
        idx = int(last[0][0] or 0) + 1
    except (TypeError, ValueError, IndexError):
        idx = 1
    row_name = frappe.generate_hash(length=10)

    frappe.db.sql(
        """
        INSERT INTO `tabqp_SP_PurchaseInvoiceComment`
        (name, parent, parentfield, parenttype, idx, message, entry_by,
         entry_date, creation, modified, modified_by, owner)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            row_name,
            doc_name,
            "comments",
            PURCHASE_INVOICE,
            idx,
            row["message"],
            row["entry_by"],
            now,
            now,
            now,
            "Administrator",
            "Administrator",
        ),
    )


def _insert_read_row(doc_name, user, now):
    """Inserta la marca de lectura como child directo."""
    try:
        last = frappe.db.sql(
            """
            SELECT COALESCE(MAX(idx), 0)
            FROM `tabqp_SP_PurchaseInvoiceCommentRead`
            WHERE parent = %s AND parenttype = %s
            """,
            (doc_name, PURCHASE_INVOICE),
        ) or [[0]]
        idx = int(last[0][0] or 0) + 1
    except (TypeError, ValueError, IndexError):
        idx = 1
    row_name = frappe.generate_hash(length=10)

    frappe.db.sql(
        """
        INSERT INTO `tabqp_SP_PurchaseInvoiceCommentRead`
        (name, parent, parentfield, parenttype, idx, user, last_read,
         creation, modified, modified_by, owner)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            row_name,
            doc_name,
            "comment_read",
            PURCHASE_INVOICE,
            idx,
            user,
            now,
            now,
            now,
            "Administrator",
            "Administrator",
        ),
    )


@frappe.whitelist()
def get_conversation(doc_name):
    """Conversacion de una factura: comentarios + no-leidos del usuario."""
    try:
        if not doc_name:
            response(400, "Falta el documento")
            return
        data = runtime.resolve().get("data")
        user = _current_user(data)
        comments = _read_comments(data, doc_name)
        unread = _unread_count(data, doc_name, user)
        response(200, data={
            "comments": comments,
            "unread_count": unread,
            "has_unread": unread > 0,
        }, msg="")
    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al obtener la conversaci\u00f3n: {}".format(str(error)))


@frappe.whitelist()
def add_comment(doc_name, comment):
    """Agrega un comentario a la factura y devuelve la lista actualizada."""
    try:
        if not doc_name:
            response(400, "Falta el documento")
            return
        comment = str(comment or "").strip()
        if not comment:
            response(400, "El comentario no puede estar vac\u00edo")
            return

        data = runtime.resolve().get("data")
        now = _now_str()
        entry_by = _own_name(data, _current_user(data))
        row = {
            "message": comment,
            "entry_by": entry_by,
            "entry_date": now,
        }

        if data is not None:
            data.insert_child(COMMENT_DOCTYPE, doc_name, row)
        else:
            _insert_comment_row(doc_name, row)

        response(
            200,
            "Comentario agregado correctamente",
            data=_read_comments(data, doc_name),
        )
    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al agregar comentario: {}".format(str(error)))


@frappe.whitelist()
def mark_conversation_read(doc_name):
    """Marca la conversacion como leida para el usuario actual."""
    try:
        if not doc_name:
            response(400, "Falta el documento")
            return
        data = runtime.resolve().get("data")
        user = _current_user(data)
        now = _now_str()

        if data is not None:
            existing = data.get_all(
                COMMENT_READ_DOCTYPE,
                filters={"parent": doc_name, "user": user},
                fields=["name"],
            )
            if existing:
                data.set_value(COMMENT_READ_DOCTYPE, existing[0]["name"], "last_read", now)
            else:
                data.insert_child(COMMENT_READ_DOCTYPE, doc_name, {
                    "user": user,
                    "last_read": now,
                })
        else:
            existing = frappe.get_all(
                COMMENT_READ_DOCTYPE,
                filters={"parent": doc_name, "user": user},
                fields=["name"],
            )
            if existing:
                frappe.db.set_value(
                    COMMENT_READ_DOCTYPE, existing[0]["name"], "last_read", now
                )
            else:
                _insert_read_row(doc_name, user, now)

        unread = _unread_count(data, doc_name, user)
        response(200, data={
            "unread_count": unread,
            "has_unread": unread > 0,
        }, msg="")
    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al marcar como le\u00eddo: {}".format(str(error)))