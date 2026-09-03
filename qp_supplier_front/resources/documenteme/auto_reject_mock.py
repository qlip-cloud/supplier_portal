# -*- coding: utf-8 -*-
"""
auto_reject_mock.py (documenteme)
=================================
Mock para probar el rechazo automatico sin llamar a documenteme.

Delega en resources/documenteme/simulation.py (build_http_double): la
inyeccion de fallos por Nvfac_cont o global vive en el modulo de
simulacion consolidado, reutilizado tambien por los tests unitarios.
"""

import frappe
from frappe import parse_json
from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.resources.documenteme.auto_reject import run_auto_reject
from qp_supplier_front.resources.documenteme import simulation


@frappe.whitelist()
def auto_reject_test(fail_cont_numbers=None, fail_all=None):
    try:
        fails = parse_json(fail_cont_numbers) if fail_cont_numbers else None
        fail_all_flag = bool(parse_json(fail_all)) if fail_all else False
        http_fn = simulation.build_http_double(
            fail_cont_numbers=fails,
            fail_all=fail_all_flag,
        )
        result = run_auto_reject(http_fn=http_fn)
        frappe.db.commit()
        response(200, "Rechazo automatico (test) ejecutado", result)

    except Exception as error:
        frappe.db.rollback()
        response(500, "Error al rechazar automaticamente (test): {}".format(str(error)))