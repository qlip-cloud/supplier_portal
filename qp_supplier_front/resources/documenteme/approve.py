# -*- coding: utf-8 -*-
"""
approve.py (documenteme) — infraestructura
==========================================
Flujo manual de aprobacion (registro en BC) de facturas documenteme.
Reutiliza el nucleo compartido _approve_base.run_approve.
"""

import frappe

from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.resources.documenteme._approve_base import run_approve


@frappe.whitelist()
def approve(doc_names):
    try:
        run_approve(doc_names)

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al aprobar: {}".format(str(error)))
