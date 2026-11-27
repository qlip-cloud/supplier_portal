# -*- coding: utf-8 -*-
"""
finalize_external.py (documenteme)
==================================
Nucleo puro del cierre externo y su reapertura.

Una factura registrada en el portal que se resolvio fuera del sistema se
cierra en el estado local "FE" (Cerrada) SIN crear en BC/GP
y SIN notificar los eventos 030/032/031/033.

El estado es terminal e inmutable: no admite sync ni ninguna otra
interaccion. La unica salida es la reapertura break-glass de un
administrador, con motivo obligatorio.

Sin imports a Frappe: funciones puras y testables en aislamiento.
"""

from qp_supplier_front.uses_cases.documenteme.notification_state import (
    is_locked,
)

STATE_EXTERNAL_CLOSED = "FE"
STATE_EXTERNAL_LABEL = "Cerrada"

# Estados desde los que se permite cerrar: antes de crear en BC/GP (BCC/PA) y
# antes de iniciar la secuencia de eventos (PR). Los finales y FE no.
EXTERNAL_CLOSE_STATES = ("E", "V", "T", "SO", "SR", "PSA")

# Si el estado previo no quedo registrado (dato legado), se reabre en
# analisis para que el pipeline normal vuelva a decidir.
REOPEN_FALLBACK_STATE = "E"


def can_finalize(state):
    """True si la factura puede cerrarse externamente en su estado actual."""
    return (state or "") in EXTERNAL_CLOSE_STATES


def can_reopen(state):
    """True si la factura puede reabrirse (solo un FE)."""
    return is_locked(state)


def build_close_fields(motive, user, previous_state, now):
    """Campos a persistir al cerrar externamente una factura.

    `qp_is_event_completed=1` deja constancia de que no hay evento DIAN en
    cola (mismo criterio que el contado finalizado).
    """
    return {
        "nvfac_esta": STATE_EXTERNAL_CLOSED,
        "qp_is_event_completed": 1,
        "qp_external_previous_state": previous_state or "",
        "qp_external_close_reason": motive,
        "qp_external_closed_by": user,
        "qp_external_closed_at": now,
    }


def reopen_state(previous_state):
    """Estado al que vuelve una factura reabierta."""
    return previous_state or REOPEN_FALLBACK_STATE


def build_reopen_fields(previous_state):
    """Campos a persistir al reabrir una factura cerrada."""
    return {
        "nvfac_esta": reopen_state(previous_state),
        "qp_is_event_completed": 0,
    }
