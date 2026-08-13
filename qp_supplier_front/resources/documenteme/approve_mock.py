# -*- coding: utf-8 -*-
"""
approve_mock.py (documenteme)
=============================
Mock de infraestructura para probar la aprobacion sin llamar a BC.
Replica el patron de reject_mock.py: provee una funcion send_request
que simula la respuesta SOAP de FacturasCompraWS con return_value.
"""

import frappe
from frappe import parse_json

from qp_supplier_front.resources.response import handler as response
from qp_supplier_front.resources.documenteme._approve_base import run_approve


_COUNTERS = {}


def _build_test_send(invoice_numbers=None):
    def send_request_status_test(endpoint_code=None, payload=None):
        count = _COUNTERS.get("approve", 0) + 1
        _COUNTERS["approve"] = count

        if count > 1:
            return {"Result": 1, "Description": "Duplicado", "invoices": []}, 200

        invoices = payload or []
        numbers = list(invoice_numbers or [])
        results = []
        for idx in range(len(invoices)):
            doc_number = numbers[idx] if idx < len(numbers) else "DOC{}".format(idx + 1)
            results.append({"doc_number": doc_number, "error": ""})
        return {"Result": 0, "invoices": results}, 200

    return send_request_status_test


@frappe.whitelist()
def approve_test(doc_names, invoice_numbers=None):
    try:
        numbers = parse_json(invoice_numbers) if invoice_numbers else None
        send_fn = _build_test_send(numbers)
        run_approve(doc_names, send_request_fn=send_fn)

    except Exception as error:
        response(500, "Error al aprobar (test): {}".format(str(error)))
