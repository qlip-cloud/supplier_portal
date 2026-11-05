# -*- coding: utf-8 -*-
"""
auto_approve_mock.py (documenteme)
=================================
Mock para probar la aprobacion automatica sin llamar a BC.

Delega en resources/documenteme/simulation.py (build_send_double) el
send_request_fn mockeado, en lugar de encolar el job real que habla con BC.
"""

import frappe
from frappe import parse_json

from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.resources.documenteme import simulation
from qp_supplier_front.resources.documenteme.auto_approve import (
    get_v_doc_names,
    is_auto_approve_enabled,
    promote_eligible_to_v,
)
from qp_supplier_front.resources.documenteme._approve_base import (
    approve_documents_core,
)


@frappe.whitelist()
def auto_approve_test(invoice_numbers=None, fail_numbers=None, fail_all=None):
    try:
        if not is_auto_approve_enabled():
            response(200, "Aprobacion automatica deshabilitada", {"skipped": True})
            return

        promoted = promote_eligible_to_v()

        doc_names = get_v_doc_names()
        if not doc_names:
            response(200, "Sin facturas en estado V", {
                "promoted": promoted,
                "approved": [],
                "errors": [],
            })
            return

        numbers = parse_json(invoice_numbers) if invoice_numbers else None
        fails = parse_json(fail_numbers) if fail_numbers else None
        fail_all_flag = bool(parse_json(fail_all)) if fail_all else False

        send_fn = simulation.build_send_double(
            numbers,
            fail_numbers=fails,
            fail_all=fail_all_flag,
        )
        result = approve_documents_core(doc_names, send_request_fn=send_fn)
        frappe.db.commit()

        response(200, "Aprobacion automatica (test) ejecutada", {
            "promoted": promoted,
            "approved": result.get("approved", []),
            "errors": result.get("errors", []),
        })

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al aprobar automaticamente (test): {}".format(str(error)))