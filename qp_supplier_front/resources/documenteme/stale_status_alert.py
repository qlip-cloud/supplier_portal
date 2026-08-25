# -*- coding: utf-8 -*-
"""
stale_status_alert.py (documenteme) — infraestructura
======================================================
Genera la alerta de estatus no definitivo (>48h) sobre las facturas de
documenteme durante la sincronizacion automatica.

Escanea qp_SP_DocumentDetail en estados de analisis ("E", "V", "T") cuya
fecha `creation` supera el umbral (48 horas) e inserta una alerta Abierta
en la child table qp_SP_Alert (reusa _alerts.insert_alert). Es idempotente:
no reinserta si ya existe una alerta abierta con el mismo mensaje.

La alerta se resuelve de forma automatica cuando la factura se aprueba o
se rechaza (resolve_open_alerts en _approve_base / auto_reject /
auto_approve_confirmation).
"""

import frappe

from qp_supplier_front.uses_cases.documenteme.stale_status_alert import (
    ANALYSIS_STATES,
    build_alert_message,
    cutoff_datetime,
    should_alert,
)
from qp_supplier_front.resources.documenteme._alerts import insert_alert


def generate_stale_status_alerts(threshold_hours=48, now=None):
    """Inserta la alerta en toda factura sin estatus definitivo > umbral.

    Retorna la lista de nombres de documentos a los que se inserto alerta.
    """
    now = now or _make_now()
    filters = {
        "nvfac_esta": ["in", list(ANALYSIS_STATES)],
        "creation": ["<=", cutoff_datetime(now, threshold_hours)],
    }
    documents = frappe.get_all(
        "qp_SP_DocumentDetail",
        filters=filters,
        fields=["name", "nvfac_nume", "creation"],
    )

    inserted = []
    for document in documents:
        if not should_alert(document, now, threshold_hours):
            continue
        message = build_alert_message(
            document.get("nvfac_nume"), document.get("name")
        )
        if _has_open_alert(frappe, document.get("name"), message):
            continue
        insert_alert(document.get("name"), message, _format_alert_date(now))
        inserted.append(document.get("name"))

    frappe.db.commit()
    return inserted


def _has_open_alert(frappe, parent_name, message):
    """True si la factura ya tiene una alerta abierta con el mismo mensaje."""
    if not parent_name:
        return False
    count = frappe.db.sql(
        """
        SELECT COUNT(*)
        FROM `tabqp_SP_Alert`
        WHERE parent = %s AND parenttype = %s
          AND alert_message = %s AND status = 'Abierta'
        """,
        (parent_name, "qp_SP_DocumentDetail", message),
    )
    return bool(count and count[0][0] > 0)


def _make_now():
    from datetime import datetime
    return datetime.now()


def _format_alert_date(now):
    return now.strftime("%Y-%m-%d %H:%M:%S")