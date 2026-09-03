# -*- coding: utf-8 -*-
"""
timeline.py (uses_cases - documenteme)
======================================
Nucleo puro del timeline de facturas documenteme: creacion de entradas
(creacion, cambio de estado, comentario) y ordenamiento descendente. Sin
frappe, sin base: recibe los valores por parametro. Los eventos documenteme
(030/032/031/033) NO forman parte del timeline.

Cada entrada es un dict:
    {
        "type": "creacion" | "estado" | "comentario",
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


def build_comment_entry(comment, user, now):
    return {
        "type": ENTRY_COMMENT,
        "message": comment or "",
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