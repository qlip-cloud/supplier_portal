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


def _build_test_send(invoice_numbers=None, fail_numbers=None, fail_all=False,
                     simulate_duplicate=False):
    """Send mockeado para la aprobacion.

    - invoice_numbers: doc_numbers a devolver por cada factura (mismo orden del payload).
    - fail_numbers: facturas (NoFacturaProveedor) que devuelven error por-factura.
    - fail_all: error global (BC rechaza el lote completo).
    - simulate_duplicate: replica el comportamiento legacy (2da llamada = duplicado).
    """
    fail_set = set(fail_numbers or [])

    def send_request_status_test(endpoint_code=None, payload=None):
        if simulate_duplicate:
            count = _COUNTERS.get("approve", 0) + 1
            _COUNTERS["approve"] = count
            if count > 1:
                return {"Result": 1, "Description": "Duplicado", "invoices": []}, 200

        if fail_all:
            return {
                "Result": 1,
                "Description": "Error global simulado al crear factura BC",
                "invoices": [],
            }, 200

        invoices = payload or []
        numbers = list(invoice_numbers or [])
        results = []
        for idx in range(len(invoices)):
            invoice = invoices[idx] if isinstance(invoices[idx], dict) else {}
            doc_number = invoice.get("NoFacturaProveedor") or "DOC{}".format(idx + 1)
            if doc_number in fail_set:
                results.append({
                    "doc_number": "",
                    "error": "Error simulado para la factura {}".format(doc_number),
                })
                continue
            doc_number = numbers[idx] if idx < len(numbers) else "DOC{}".format(idx + 1)
            results.append({"doc_number": doc_number, "error": ""})
        return {"Result": 0, "invoices": results}, 200

    return send_request_status_test


@frappe.whitelist()
def approve_test(doc_names, invoice_numbers=None, fail_numbers=None, fail_all=None):
    try:
        numbers = parse_json(invoice_numbers) if invoice_numbers else None
        fails = parse_json(fail_numbers) if fail_numbers else None
        fail_all_flag = bool(parse_json(fail_all)) if fail_all else False
        send_fn = _build_test_send(numbers, fail_numbers=fails, fail_all=fail_all_flag)
        run_approve(doc_names, send_request_fn=send_fn)

    except Exception as error:
        response(500, "Error al aprobar (test): {}".format(str(error)))
