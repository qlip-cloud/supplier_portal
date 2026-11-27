# -*- coding: utf-8 -*-
"""
immutability.py (documenteme)
=============================
Hook `validate` de `qp_SP_DocumentDetail`: una factura en estado bloqueado
(`FE`, Cerrada) no puede volver a guardarse.

Es la defensa en profundidad del cierre externo: aunque un proceso de sync,
una tarea automatica o un script olvide su propia guarda, ningun `save()`
puede modificar una FE. La unica excepcion es la reapertura break-glass,
que marca explicitamente `doc.flags.allow_external_reopen`.
"""

import frappe

from qp_supplier_front.uses_cases.documenteme.notification_state import (
    is_locked,
)

DOCUMENT_DETAIL = "qp_SP_DocumentDetail"
LOCKED_MESSAGE = (
    "La factura está cerrada y no admite cambios. "
    "Solo un administrador puede reabrirla."
)


def _allow_reopen(doc):
    flags = getattr(doc, "flags", None)
    return bool(getattr(flags, "allow_external_reopen", False))


def validate(doc, method=None):
    """Rechaza cualquier save de un documento que ya estaba bloqueado."""
    if doc is None or getattr(doc, "doctype", None) != DOCUMENT_DETAIL:
        return
    previous = doc.get_doc_before_save()
    if previous is None:
        return
    if not is_locked(previous.get("nvfac_esta")):
        return
    if _allow_reopen(doc):
        return
    frappe.throw(LOCKED_MESSAGE)
