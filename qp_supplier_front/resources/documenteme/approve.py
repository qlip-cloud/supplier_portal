# -*- coding: utf-8 -*-
"""
approve.py (documenteme) — infraestructura
==========================================
Flujo manual de aprobacion (registro en BC) de facturas documenteme.
Reutiliza el nucleo compartido _approve_base.run_approve.

- validate(doc_names): pre-validacion sin efectos secundarios. Devuelve las
  advertencias que impedirian la aprobacion automatica (regla OC - recepcion
  - montos) para que el front las muestre en un confirm.
- approve(doc_names, force): aprueba el lote. Con force=True el usuario ya
  confirmo las violaciones y se omiten las advertencias (los estados
  definitivos/en proceso siguen bloqueando).
"""

import frappe
from frappe import parse_json

from qp_supplier_front.resources.documenteme._approve_base import (
    _has_permission,
    collect_document_violations,
    run_approve,
)
from qp_supplier_front.resources.response import handler as response


@frappe.whitelist()
def validate(doc_names):
    try:
        if not _has_permission(frappe.get_roles()):
            response(403, "No tiene permisos para aprobar facturas")
            return

        violation_docs = collect_document_violations(parse_json(doc_names))
        response(200, "ok", {"violations": violation_docs})

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al validar: {}".format(str(error)))


@frappe.whitelist()
def approve(doc_names, force=False, backend=None):
    try:
        force = parse_json(force) if force else False
        backend = resolve_backend(backend)
        run_approve(doc_names, force=force, backend=backend)

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al aprobar: {}".format(str(error)))


def resolve_backend(backend=None):
    """Backend de creacion de facturas (BC/GP) o el default del MasterSetup.

    Si el campo no puede leerse (columna ausente / error) se asume BC.
    """
    if backend:
        return str(backend).upper()
    try:
        value = frappe.db.get_single_value(
            "qp_SP_MasterSetup", "documenteme_backend"
        )
    except Exception:
        return "BC"
    return (value or "BC").upper()


@frappe.whitelist()
def default_backend():
    """Backend predeterminado para el selector manual del front."""
    return resolve_backend()