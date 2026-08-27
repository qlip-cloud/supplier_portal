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
def approve(doc_names, force=False):
    try:
        force = parse_json(force) if force else False
        run_approve(doc_names, force=force)

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al aprobar: {}".format(str(error)))