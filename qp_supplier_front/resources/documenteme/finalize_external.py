# -*- coding: utf-8 -*-
"""
finalize_external.py (documenteme) - recursos
=============================================
Cierre externo de una factura documenteme y su reapertura break-glass.

Cerrar:
  - Marca la factura en `FE` (Cerrada).
  - NO crea la factura en BC/GP ni programa/envia ningun evento
    030/032/031/033.
  - Deja auditoria (motivo, autor, fecha, estado previo), resuelve alertas y
    libera las recepciones reservadas.
  - A partir de ahi la factura es terminal e inmutable (ver immutability.py).

Reabrir:
  - Solo un administrador (Administrador Documenteme / Administrator).
  - Exige motivo, restaura el estado previo y deja constancia en el timeline.

Roles permitidos para ambas acciones: `can_see_all_documenteme`
(Administrator + Administrador Documenteme). Administrador Sede/Compras NO.
"""

from datetime import datetime

import frappe

from qp_supplier_front.infrastructure.adapters.timeline_adapter import (
    RealTimelineAdapter,
)
from qp_supplier_front.resources.documenteme._alerts import resolve_open_alerts
from qp_supplier_front.resources.documenteme._reject_base import (
    _release_claimed_receipts,
)
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.services.documenteme_access import (
    can_see_all_documenteme,
)
from qp_supplier_front.uses_cases.documenteme.finalize_external import (
    build_close_fields,
    build_reopen_fields,
    can_finalize,
    can_reopen,
)

DOCUMENT_DETAIL = "qp_SP_DocumentDetail"


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _has_permission(user_roles):
    return can_see_all_documenteme(user_roles)


def _clean_motive(motive):
    return str(motive or "").strip()


def _clear_event_schedule(doc):
    """Limpieza defensiva de la programacion de eventos.

    Cerrar solo se permite antes de BCC/PA/PR, por lo que no deberia haber
    eventos programados; se limpia igual para que un estado legado no quede
    con un job pendiente.
    """
    doc.qp_event_sequence = None
    doc.qp_event_pending_code = None
    doc.qp_event_next_at = None
    doc.qp_event_attempts = 0


def _history(doc_name, message):
    RealTimelineAdapter(frappe_module=frappe).add_user_assignment(
        doc_name, message, user=frappe.session.user
    )


@frappe.whitelist()
def finalize_external(doc_name, motive):
    """Cierra una factura sin crear en BC/GP ni notificar a documenteme."""
    try:
        if not _has_permission(frappe.get_roles()):
            response(403, "No tiene permisos para cerrar facturas externamente")
            return

        if not doc_name:
            response(400, "Falta el documento")
            return

        motive = _clean_motive(motive)
        if not motive:
            response(400, "El motivo del cierre externo es obligatorio")
            return

        doc = frappe.get_doc(DOCUMENT_DETAIL, doc_name)
        previous_state = doc.get("nvfac_esta")
        if not can_finalize(previous_state):
            response(
                400,
                "La factura no se puede cerrar externamente en su estado actual ({})".format(
                    previous_state or "-"
                ),
                {"state": previous_state},
            )
            return

        fields = build_close_fields(
            motive, frappe.session.user, previous_state, _now()
        )
        for field, value in fields.items():
            setattr(doc, field, value)
        _clear_event_schedule(doc)
        doc.save()

        _release_claimed_receipts(doc)
        resolve_open_alerts(doc.name)
        _history(
            doc.name,
            "Factura cerrada: {}".format(motive),
        )

        frappe.db.commit()
        response(
            200,
            "Factura cerrada",
            {"closed": [doc.name], "previous_state": previous_state},
        )

    except Exception as error:
        frappe.db.rollback()
        response(
            500,
            "Error al cerrar la factura externamente: {}".format(str(error)),
        )


@frappe.whitelist()
def reopen_external(doc_name, motive):
    """Reabre (break-glass) una factura cerrada."""
    try:
        if not _has_permission(frappe.get_roles()):
            response(403, "No tiene permisos para reabrir facturas")
            return

        if not doc_name:
            response(400, "Falta el documento")
            return

        motive = _clean_motive(motive)
        if not motive:
            response(400, "El motivo de la reapertura es obligatorio")
            return

        doc = frappe.get_doc(DOCUMENT_DETAIL, doc_name)
        if not can_reopen(doc.get("nvfac_esta")):
            response(
                400,
                "La factura no está cerrada externamente",
                {"state": doc.get("nvfac_esta")},
            )
            return

        previous_state = doc.get("qp_external_previous_state")
        fields = build_reopen_fields(previous_state)

        # Unica via que el hook validate acepta para salir de FE.
        doc.flags.allow_external_reopen = True
        for field, value in fields.items():
            setattr(doc, field, value)
        _clear_event_schedule(doc)
        doc.save()

        _history(
            doc.name,
            "Factura reabierta (estaba cerrada): {}".format(
                motive
            ),
        )

        frappe.db.commit()
        response(
            200,
            "Factura reabierta",
            {"state": fields.get("nvfac_esta")},
        )

    except Exception as error:
        frappe.db.rollback()
        response(
            500,
            "Error al reabrir la factura: {}".format(str(error)),
        )
