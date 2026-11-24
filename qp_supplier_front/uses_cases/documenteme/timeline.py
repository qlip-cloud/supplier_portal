# -*- coding: utf-8 -*-
"""
timeline.py (uses_cases - documenteme)
======================================
Nucleo puro del timeline de facturas documenteme: creacion de entradas
(creacion, cambio de estado, comentario) y ordenamiento descendente. Sin
frappe, sin base: recibe los valores por parametro. Los event_logs de
documenteme (030/032/031/033) NO forman parte del timeline; si se registra
una entrada de origen "documenteme" cuando una sincronizacion trae un
nvfac_ueve (o un estado final) para dejar constancia de que no fue una
peticion nuestra.

Cada entrada es un dict:
    {
        "type": "creacion" | "estado" | "comentario" | "documenteme",
        "message": str,
        "old_state": str|None,
        "new_state": str|None,
        "entry_by": str,
        "entry_date": str "YYYY-MM-DD HH:MM:SS",
    }
"""

ENTRY_CREATION = "creacion"
ENTRY_STATE = "estado"
ENTRY_COMMENT = "comentario"
ENTRY_ASSIGNMENT = "asignacion"
ENTRY_USER_ASSIGNMENT = "asignacion_usuario"
ENTRY_DOCUMENTEME = "documenteme"

CREATION_MESSAGE = "Factura registrada en el sistema"

# Etiquetas de estado identicas a las que se muestran al usuario en la vista
# (list.html / select de estado) para que el timeline diga lo mismo que el app.
STATE_LABELS = {
    "A": "Aprobado",
    "E": "Registrado",
    "V": "Lista para Registro",
    "R": "Rechazada",
    "BCC": "Creada en BC",
    "PA": "En proceso de aprobación",
    "PR": "En proceso de rechazo",
    "PSA": "Por Autorización",
    "SR": "Sin referencia",
    "SO": "Sin OC",
    "T": "",
}


def state_label(code):
    return STATE_LABELS.get(code or "", "") or (code or "-")


def build_creation_entry(state, user, now):
    return {
        "type": ENTRY_CREATION,
        "message": CREATION_MESSAGE,
        "old_state": None,
        "new_state": state or None,
        "entry_by": user or "",
        "entry_date": now or "",
    }


def build_state_entry(old_state, new_state, user, now):
    return {
        "type": ENTRY_STATE,
        "message": "Cambio de estado: {0} -> {1}".format(
            state_label(old_state), state_label(new_state)
        ),
        "old_state": old_state or None,
        "new_state": new_state or None,
        "entry_by": user or "",
        "entry_date": now or "",
    }


def build_comment_entry(comment, user, now, attachment_file_id="",
                        attachment_file_url="", attachment_file_name=""):
    return {
        "type": ENTRY_COMMENT,
        "message": comment or "",
        "old_state": None,
        "new_state": None,
        "entry_by": user or "",
        "entry_date": now or "",
        "attachment_file_id": attachment_file_id or "",
        "attachment_file_url": attachment_file_url or "",
        "attachment_file_name": attachment_file_name or "",
    }


def build_assignment_entry(message, user, now):
    """Entrada de historial (no comentario) para eventos del flujo.

    Se muestra en el "Historial" del modal de alertas sin abrir una alerta:
    no pinta el icono ni aparece en la conversacion.
    """
    return {
        "type": ENTRY_ASSIGNMENT,
        "message": message or "",
        "old_state": None,
        "new_state": None,
        "entry_by": user or "",
        "entry_date": now or "",
    }


def user_assignment_message(new_labels, previous_labels):
    """Mensaje del historial para una asignacion manual de usuarios.

    Lista los asignados nuevos y, si habia, los previos (reasignacion).
    El autor de la entrada lo agrega el timeline (`entry_by`).
    """
    assigned = ", ".join(
        [label for label in (new_labels or []) if label]
    ) or "-"
    previous = [label for label in (previous_labels or []) if label]
    if not previous:
        return "Asignados: {0}.".format(assigned)
    return "Asignados: {0}. Asignados previos: {1}.".format(
        assigned, ", ".join(previous))


def build_documenteme_entry(code, previous_state, current_state, user, now):
    """Entrada de historial que registra un dato traido por la sincronizacion.

    Deja constancia de que el `nvfac_ueve` (o el estado final) lo reporto
    documenteme y no fue una peticion nuestra. Si la reconciliacion cambio el
    estado local, el mensaje incluye la transicion.
    """
    from qp_supplier_front.uses_cases.documenteme.event_notifier import (
        DOCUMENTEME_EVENT_STATES,
    )

    code = (code or "").strip()
    event_state = DOCUMENTEME_EVENT_STATES.get(code)
    label = (
        state_label(current_state)
        or state_label(event_state)
        or (current_state or "")
    )
    if code:
        message = "Documenteme reportó el evento {0} ({1}) al sincronizar.".format(
            code, label
        )
    else:
        message = "Documenteme reportó el estado {0} al sincronizar.".format(
            label or "-"
        )
    if (previous_state or "") != (current_state or ""):
        message += " Cambio de estado: {0} -> {1}.".format(
            state_label(previous_state), state_label(current_state)
        )
    return {
        "type": ENTRY_DOCUMENTEME,
        "message": message,
        "old_state": None,
        "new_state": None,
        "entry_by": user or "Documenteme",
        "entry_date": now or "",
    }


def build_user_assignment_entry(message, user, now):
    """Entrada de historial (no comentario) de una asignacion manual."""
    return {
        "type": ENTRY_USER_ASSIGNMENT,
        "message": message or "",
        "old_state": None,
        "new_state": None,
        "entry_by": user or "",
        "entry_date": now or "",
    }


def order_desc(entries):
    """Ordena las entradas de la mas reciente a la mas antigua por entry_date.

    entry_date es un string "YYYY-MM-DD HH:MM:SS" (orden lexicografico ==
    cronologico). El algoritmo es estable: las entradas con la misma fecha
    mantienen su orden relativo (una por cada transicion).
    """
    return sorted(entries, key=lambda entry: entry.get("entry_date") or "", reverse=True)