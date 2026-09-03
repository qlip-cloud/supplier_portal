# -*- coding: utf-8 -*-
"""timeline.py (documenteme) - recursos
========================================
Servicios entrantes del timeline de facturas documenteme:

  - get_timeline(doc_name): lista el historial (creacion, cambios de estado,
    comentarios y eventos documenteme) de una factura, de la mas reciente a la
    mas antigua.
  - add_comment(doc_name, comment): agrega un comentario a una factura.
  - on_document_before_save(doc, method): hook before_save de
    qp_SP_DocumentDetail que registra la creacion del documento y los cambios
    de estado que se persisten via doc.save() (modo real).

La persistencia va por el adaptador de timeline (real o in-memory segun el
flag de simulacion). El hook usa SIEMPRE el adaptador real porque solo se
dispara ante saves reales de Frappe.
"""

import frappe

from qp_supplier_front.infrastructure.adapters.timeline_adapter import (
    RealTimelineAdapter,
    _user_name,
    _now_str,
)
from qp_supplier_front.resources.documenteme import runtime
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.uses_cases.documenteme.event_logs import (
    notification_summary,
    notification_timeline,
    resolve_sequence,
)
from qp_supplier_front.uses_cases.documenteme.timeline import (
    build_creation_entry,
    build_state_entry,
)

DOCUMENT_DETAIL = "qp_SP_DocumentDetail"
DOCUMENT_EVENT_LOG = "qp_SP_EventLog"
DOCUMENT_ALERT = "qp_SP_Alert"


def _timeline(data):
    """Adaptador de timeline: memoria en simulacion, frappe en real."""
    if data is not None:
        return data.timeline
    return RealTimelineAdapter()


def _read(data, doctype, filters, fields, order_by=None):
    """Lectura get_all del facade (data) o de frappe real."""
    if data is not None:
        return data.get_all(
            doctype, filters=filters, fields=fields, order_by=order_by
        )
    return frappe.get_all(
        doctype, filters=filters, fields=fields, order_by=order_by
    )


def _doc_state(data, doc_name):
    if data is not None:
        return data.get_value(DOCUMENT_DETAIL, doc_name, "nvfac_esta") or ""
    return frappe.db.get_value(DOCUMENT_DETAIL, doc_name, "nvfac_esta") or ""


@frappe.whitelist()
def get_timeline(doc_name):
    try:
        if not doc_name:
            response(400, "Falta el documento")
            return
        data = runtime.resolve().get("data")
        entries = _timeline(data).get(doc_name)
        response(200, data=entries, msg="")
    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al obtener el historial: {}".format(str(error)))


@frappe.whitelist()
def add_comment(doc_name, comment):
    try:
        if not doc_name:
            response(400, "Falta el documento")
            return
        comment = str(comment or "").strip()
        if not comment:
            response(400, "El comentario no puede estar vac\u00edo")
            return
        data = runtime.resolve().get("data")
        _timeline(data).add_comment(doc_name, comment)
        if data is not None:
            data.commit()
        else:
            frappe.db.commit()
        response(
            200,
            "Comentario agregado correctamente",
            data=_timeline(data).get_comments(doc_name),
        )
    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al agregar comentario: {}".format(str(error)))


def on_document_before_save(doc, method):
    """Hook before_save de qp_SP_DocumentDetail (modo real).

    - Documento nuevo: registra la entrada de creacion.
    - Documento existente con cambio de nvfac_esta: registra la entrada de
      cambio de estado. El hook agrega la fila al child timeline; el save en
      curso la persiste (sin re-save, sin recursion).
    """
    if doc is None or getattr(doc, "doctype", None) != DOCUMENT_DETAIL:
        return

    user = _user_name(frappe.session.user)
    now = _now_str()
    previous = doc.get_doc_before_save()

    if previous is None:
        doc.append("timeline", build_creation_entry(doc.get("nvfac_esta"), user, now))
        return

    old_state = previous.get("nvfac_esta")
    new_state = doc.get("nvfac_esta")
    if (old_state or "") != (new_state or ""):
        doc.append("timeline", build_state_entry(old_state, new_state, user, now))


@frappe.whitelist()
def get_conversation(doc_name):
    """Conversacion de una factura: SOLO comentarios + lectura del usuario."""
    try:
        if not doc_name:
            response(400, "Falta el documento")
            return
        data = runtime.resolve().get("data")
        adapter = _timeline(data)
        comments = adapter.get_comments(doc_name)
        unread = adapter.unread_count(doc_name)
        response(200, data={
            "comments": comments,
            "unread_count": unread,
            "has_unread": unread > 0,
        }, msg="")
    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al obtener la conversacion: {}".format(str(error)))


@frappe.whitelist()
def mark_conversation_read(doc_name):
    """Marca la conversacion como leida para el usuario actual."""
    try:
        if not doc_name:
            response(400, "Falta el documento")
            return
        data = runtime.resolve().get("data")
        adapter = _timeline(data)
        adapter.mark_read(doc_name)
        if data is not None:
            data.commit()
        else:
            frappe.db.commit()
        unread = adapter.unread_count(doc_name)
        response(200, data={
            "unread_count": unread,
            "has_unread": unread > 0,
        }, msg="")
    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al marcar como leido: {}".format(str(error)))


@frappe.whitelist()
def get_notifications(doc_name):
    """Timeline de notificaciones de una factura documenteme.

    Retorna el resumen de la notificacion (030/032/033/031), el historial de
    reintentos (event_logs), las entradas de creacion/cambio de estado y las
    alertas abiertas. Es la fuente del modal que abre el icono de alerta.
    """
    try:
        if not doc_name:
            response(400, "Falta el documento")
            return
        data = runtime.resolve().get("data")
        doc_state = _doc_state(data, doc_name)

        events = _read(
            data,
            DOCUMENT_EVENT_LOG,
            filters={"parent": doc_name},
            fields=["event_code", "status", "response", "attempt_date",
                    "error_message"],
            order_by="attempt_date asc",
        )
        alerts = _read(
            data,
            DOCUMENT_ALERT,
            filters={"parent": doc_name, "status": "Abierta"},
            fields=["alert_date", "alert_message", "alert_type"],
            order_by="alert_date desc",
        )

        sequence = resolve_sequence(doc_state, events)
        summary = notification_summary(events, sequence, doc_state)
        timeline_rows = notification_timeline(events, sequence, doc_state)
        timeline_rows.reverse()

        state_entries = [
            entry for entry in _timeline(data).get(doc_name)
            if entry.get("type") != "comentario"
        ]

        response(200, data={
            "summary": summary,
            "events": timeline_rows,
            "state_entries": state_entries,
            "alerts": alerts,
        }, msg="")
    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al obtener notificaciones: {}".format(str(error)))