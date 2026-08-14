# -*- coding: utf-8 -*-
"""
_alerts.py (documenteme)
========================
Helpers de infraestructura para la tabla de alertas de las facturas
documenteme (qp_SP_Alert, child table de qp_SP_DocumentDetail).

Una alerta guarda mensaje + fecha + estatus (Abierta/Resuelta). Las abiertas
se muestran en el tooltip del listado; se resuelven cuando la factura se
aprueba (o se rechaza).
"""

import frappe


def insert_alert(parent_name, message, now):
    """Inserta una alerta Abierta en la child table de la factura."""
    if not parent_name:
        return

    last = frappe.db.sql(
        """
        SELECT COALESCE(MAX(idx), 0)
        FROM `tabqp_SP_Alert`
        WHERE parent = %s AND parenttype = %s
        """,
        (parent_name, "qp_SP_DocumentDetail"),
    )
    idx = int(last[0][0] or 0) + 1
    alert_name = frappe.generate_hash(length=10)

    frappe.db.sql(
        """
        INSERT INTO `tabqp_SP_Alert`
        (name, parent, parentfield, parenttype, idx, alert_date, alert_message, status,
         creation, modified, modified_by, owner)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            alert_name,
            parent_name,
            "alertas",
            "qp_SP_DocumentDetail",
            idx,
            now,
            message,
            "Abierta",
            now,
            now,
            "Administrator",
            "Administrator",
        ),
    )


def resolve_open_alerts(parent_name):
    """Marca como Resuelta las alertas abiertas de la factura."""
    if not parent_name:
        return

    frappe.db.sql(
        """
        UPDATE `tabqp_SP_Alert`
        SET status = 'Resuelta', modified = %s
        WHERE parent = %s AND parenttype = %s AND status = 'Abierta'
        """,
        (
            _make_now(),
            parent_name,
            "qp_SP_DocumentDetail",
        ),
    )


def _make_now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
