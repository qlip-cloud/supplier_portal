# -*- coding: utf-8 -*-
"""
approve_mock.py (documenteme)
=============================
Mock de infraestructura para probar la aprobacion sin llamar a BC.

Delega en resources/documenteme/simulation.py (build_send_double): el
helper de mocking y la inyeccion de fallos viven en el modulo de
simulacion consolidado, reutilizados tambien por los tests unitarios.
"""

import frappe
from frappe import parse_json

from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.resources.documenteme._approve_base import run_approve
from qp_supplier_front.resources.documenteme import simulation


@frappe.whitelist()
def approve_test(doc_names, invoice_numbers=None, fail_numbers=None, fail_all=None):
    try:
        numbers = parse_json(invoice_numbers) if invoice_numbers else None
        fails = parse_json(fail_numbers) if fail_numbers else None
        fail_all_flag = bool(parse_json(fail_all)) if fail_all else False
        send_fn = simulation.build_send_double(
            numbers,
            fail_numbers=fails,
            fail_all=fail_all_flag,
        )
        run_approve(doc_names, send_request_fn=send_fn)

    except Exception as error:
        response(500, "Error al aprobar (test): {}".format(str(error)))