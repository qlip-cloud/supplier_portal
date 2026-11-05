# -*- coding: utf-8 -*-
"""
approve_confirmation.py (documenteme)
=====================================
Nucleo puro del flujo de confirmacion de facturas documenteme creadas en BC.

El flujo de aprobacion completo es:
  1. Crear en BC (flujo existente approve / auto_approve) que marca el
     documento con estado "BCC" (Creada en BC) y guarda el invoice_id que
     BC devuelve en qp_SP_PurchaseInvoice.invoice_id.
  2. Un servicio externo notifica la confirmacion llamando al endpoint
     update_document con (invoice_id, confirmation_id). Este servicio:
       - localiza la factura por invoice_id,
       - guarda el confirmation_id recibido en qp_SP_PurchaseInvoice,
       - marca el documento en estado "PA" (En proceso de Aprobacion), y
       - encola el job asincronico que notifica la aprobacion a documenteme
         (secuencia 030 -> 032 -> 033).
  3. Si la notificacion a documenteme tiene exito, el documento pasa a "A"
     (Aprobado) con nvfac_ueve "033". Si falla tras los reintentos, se
     registra una alerta y el documento permanece en "PA".

No importa Frappe. Todas las dependencias de infraestructura (DB, API,
encolado) se inyectan como callbacks para poder probarse de forma aislada.
"""

PENDING_APPROVAL_STATE = "PA"
CREATED_IN_BC_STATE = "BCC"
APPROVED_FINAL_STATE = "A"
APPROVAL_FINAL_EVENT = "033"

CONFIRMATION_STATES = (CREATED_IN_BC_STATE, PENDING_APPROVAL_STATE)


def _clean(value):
    return (value or "").strip()


def validate_confirmation(invoice_id, confirmation_id):
    """Valida los parametros entrantes. Retorna lista de errores (vacia si ok)."""
    errors = []
    if not _clean(invoice_id):
        errors.append("invoice_id es requerido")
    if not _clean(confirmation_id):
        errors.append("confirmation_id es requerido")
    return errors


def is_approval_candidate(state):
    """Solo los estados intermedios del flujo de aprobacion son candidatos
    a confirmar: Creada en BC o En proceso de Aprobacion."""
    return state in CONFIRMATION_STATES


def process_confirmation(
    invoice_id,
    confirmation_id,
    find_document_fn,
    set_confirmation_id_fn,
    mark_pending_approval_fn,
    enqueue_approve_fn,
    commit_fn,
):
    """Orquesta la confirmacion de una factura creada en BC.

    Retorna {"ok": bool, "errors": [...], "doc": doc|None}.
    """
    errors = validate_confirmation(invoice_id, confirmation_id)
    if errors:
        return {"ok": False, "errors": errors, "doc": None}

    invoice_id = _clean(invoice_id)
    confirmation_id = _clean(confirmation_id)

    doc = find_document_fn(invoice_id)
    if not doc:
        return {
            "ok": False,
            "errors": [
                "No se encontro una factura con invoice_id {}".format(invoice_id)
            ],
            "doc": None,
        }

    set_confirmation_id_fn(doc, confirmation_id)
    mark_pending_approval_fn(doc)
    enqueue_approve_fn(doc)
    commit_fn()

    return {"ok": True, "errors": [], "doc": doc}


def is_approval_successful(invoice_id, get_last_event_fn):
    """True si el documento ya quedo aprobado en documenteme (nueve 033)."""
    return get_last_event_fn(invoice_id) == APPROVAL_FINAL_EVENT
