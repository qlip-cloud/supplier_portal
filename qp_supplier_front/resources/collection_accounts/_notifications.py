# -*- coding: utf-8 -*-
"""
_notifications.py (resources/collection_accounts)
=================================================
Helpers de infraestructura para las notificaciones de las facturas de
cuentas de cobro (qp_SP_PurchaseInvoiceNotification, child table de
qp_SP_PurchaseInvoice).

Una notificacion guarda mensaje + fecha + tipo (Alerta/ErrorUrgente) + estado
(Abierta/Resuelta). Las abiertas se muestran en el icono de la columna
"Notificaciones" del front; se resuelven cuando la factura se aprueba (o se
confirma la creacion en BC).
"""

import frappe


def _make_now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def insert_notification(parent_name, message, now=None, notification_type="Alerta"):
    """Inserta una notificacion Abierta en la child table de la factura."""
    if not parent_name or not message:
        return

    now = now or _make_now()
    last = frappe.db.sql(
        """
        SELECT COALESCE(MAX(idx), 0)
        FROM `tabqp_SP_PurchaseInvoiceNotification`
        WHERE parent = %s AND parenttype = %s
        """,
        (parent_name, "qp_SP_PurchaseInvoice"),
    )
    idx = int(last[0][0] or 0) + 1
    notification_name = frappe.generate_hash(length=10)

    frappe.db.sql(
        """
        INSERT INTO `tabqp_SP_PurchaseInvoiceNotification`
        (name, parent, parentfield, parenttype, idx, notification_date,
         notification_type, notification_message, status,
         creation, modified, modified_by, owner)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            notification_name,
            parent_name,
            "notifications",
            "qp_SP_PurchaseInvoice",
            idx,
            now,
            notification_type,
            message,
            "Abierta",
            now,
            now,
            "Administrator",
            "Administrator",
        ),
    )


def resolve_open_notifications(parent_name):
    """Marca como Resuelta las notificaciones abiertas de la factura."""
    if not parent_name:
        return

    frappe.db.sql(
        """
        UPDATE `tabqp_SP_PurchaseInvoiceNotification`
        SET status = 'Resuelta', modified = %s
        WHERE parent = %s AND parenttype = %s AND status = 'Abierta'
        """,
        (
            _make_now(),
            parent_name,
            "qp_SP_PurchaseInvoice",
        ),
    )