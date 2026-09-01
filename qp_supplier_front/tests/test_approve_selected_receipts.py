# -*- coding: utf-8 -*-
"""
test_approve_selected_receipts.py
=================================
Pruebas del pipeline de aprobacion con seleccion manual explicita
(approve_documents + selected_receipts): la combinacion la elige el usuario
y NO se re-runnea pack_oc_group.

Nucleo puro: no requiere Frappe ni base de datos.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_approve_selected_receipts.py -v
"""
import unittest

from qp_supplier_front.uses_cases.documenteme.approve import approve_documents


def _doc(**overrides):
    data = {
        "name": "DOC1",
        "nvfac_nume": "FAC001",
        "nvpro_ndoc": "900000001",
        "nvfac_fech": "2026-07-09 10:00:00",
        "nvtip_docu": "F",
        "nvfac_orde": "PO1",
        "nvfac_esta": "V",
        "nvfac_conv": "2",
        "nvfac_stot": 100,
        "nvfac_totp": 119,
        "nvfac_viva": 19,
    }
    data.update(overrides)
    return data


def _receipt(name, amount, qp_invoice=None):
    return {"name": name, "amount": amount, "date": "2026-01-01",
            "qp_invoice": qp_invoice}


def _callbacks(docs, bank, invoice_results=None, status=200):
    calls = {"commits": 0}

    def get_docs_fn(names):
        return [doc for doc in docs if doc.get("name") in list(names)]

    def get_lines_fn(doc):
        return [{
            "item_code": "M1", "qty": 1, "rate": 100, "idx": 1,
            "receiving_no": "R1", "order_no": "PO1",
        }], ""

    def get_headquarter_fn(purchase_order):
        return "HQ01"

    def po_exists_fn(purchase_order):
        return bool(purchase_order)

    def receipts_total_fn(purchase_order):
        return 100

    results = invoice_results if invoice_results is not None else [
        {"doc_number": "BC1", "error": ""}
    ]

    def send_request_fn(endpoint_code, payload):
        return {"Result": 0, "invoices": results}, status

    def parse_doc_numbers_fn(resp):
        return results

    def persist_invoice_fn(doc, doc_number, now):
        calls.setdefault("persisted", []).append(doc.get("nvfac_nume"))

    def mark_registered_fn(doc, doc_number):
        calls.setdefault("marked", []).append(doc.get("nvfac_nume"))

    def mark_error_fn(doc, error):
        calls.setdefault("errors", []).append((doc.get("nvfac_nume"), error))

    def commit_fn():
        calls["commits"] += 1

    return calls, {
        "get_docs_fn": get_docs_fn,
        "get_lines_fn": get_lines_fn,
        "get_headquarter_fn": get_headquarter_fn,
        "po_exists_fn": po_exists_fn,
        "receipts_total_fn": receipts_total_fn,
        "receipt_bank_fn": lambda po: bank,
        "consume_receipts_fn": lambda doc, names: calls.setdefault(
            "consumed", []).append(names),
        "send_request_fn": send_request_fn,
        "parse_doc_numbers_fn": parse_doc_numbers_fn,
        "persist_invoice_fn": persist_invoice_fn,
        "mark_registered_fn": mark_registered_fn,
        "mark_error_fn": mark_error_fn,
        "commit_fn": commit_fn,
    }


class TestApproveSelected(unittest.TestCase):

    def test_seleccion_completa_aprueba(self):
        docs = [_doc()]
        bank = [_receipt("R1", 40), _receipt("R2", 60), _receipt("R3", 10)]
        calls, kwargs = _callbacks(docs, bank)
        result = approve_documents(
            ["DOC1"], now="2026-01-01 10:00:00",
            selected_receipts={"DOC1": ["R1", "R2"]}, **kwargs,
        )
        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(result["errors"], [])
        self.assertIn("FAC001", calls.get("marked", []))
        # El consumo solo toca los recibos elegidos (no pack_oc_group).
        self.assertEqual(calls.get("consumed"), [["R1", "R2"]])

    def test_seleccion_parcial_no_aprueba(self):
        docs = [_doc()]
        bank = [_receipt("R1", 40), _receipt("R2", 60)]
        calls, kwargs = _callbacks(docs, bank)
        result = approve_documents(
            ["DOC1"], now="2026-01-01 10:00:00",
            selected_receipts={"DOC1": ["R1"]}, **kwargs,
        )
        self.assertEqual(result["approved"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("no cubre", result["errors"][0]["error"])

    def test_seleccion_excede_no_aprueba(self):
        docs = [_doc()]
        bank = [_receipt("R1", 140)]
        calls, kwargs = _callbacks(docs, bank)
        result = approve_documents(
            ["DOC1"], now="2026-01-01 10:00:00",
            selected_receipts={"DOC1": ["R1"]}, **kwargs,
        )
        self.assertEqual(result["approved"], [])
        self.assertGreater(len(result["errors"]), 0)

    def test_recibo_reclamado_por_otra_factura_no_aprueba(self):
        docs = [_doc()]
        bank = [_receipt("R1", 100, qp_invoice="OTHER")]
        calls, kwargs = _callbacks(docs, bank)
        result = approve_documents(
            ["DOC1"], now="2026-01-01 10:00:00",
            selected_receipts={"DOC1": ["R1"]}, **kwargs,
        )
        self.assertEqual(result["approved"], [])
        self.assertIn("no están disponibles", result["errors"][0]["error"])

    def test_sin_recepciones_seleccionadas_no_aprueba(self):
        docs = [_doc()]
        bank = [_receipt("R1", 100)]
        calls, kwargs = _callbacks(docs, bank)
        result = approve_documents(
            ["DOC1"], now="2026-01-01 10:00:00",
            selected_receipts={}, **kwargs,
        )
        self.assertEqual(result["approved"], [])


if __name__ == "__main__":
    unittest.main()