# -*- coding: utf-8 -*-
"""
tests/test_payload_adapter.py
=============================
Tests puros del adaptador de payload de facturas BC (make_invoice_builder):
el flujo documenteme mantiene "puntofacturacion": "estandar" y el flujo de
cuentas de cobro (collection) genera "DS SOPORTE". No requiere Frappe.
"""
import unittest

from qp_supplier_front.uses_cases.collection_invoices.approve import (
    approve_collection_invoices,
)
from qp_supplier_front.uses_cases.documenteme.approve import (
    build_payload,
    make_invoice_builder,
)


def _doc(**overrides):
    data = {
        "name": "DOC1",
        "nvfac_nume": "FAC001",
        "nvpro_ndoc": "050633410",
        "nvfac_fech": "2026-07-09 10:00:00",
        "nvfac_orde": "45238",
        "nvfac_rece": "R108349",
        "nvfac_stot": 50000,
        "nvfac_viva": 0,
        "nvfac_totp": 50000,
        "nvfac_conv": "2",
        "nvfac_esta": "E",
        "nvmon_codi": "COP",
    }
    data.update(overrides)
    return data


def _line(**overrides):
    data = {
        "item_code": "M000455",
        "qty": 1,
        "rate": 50000.0,
        "idx": 0,
        "receiving_no": "R108349",
        "order_no": "45238",
    }
    data.update(overrides)
    return data


class TestMakeInvoiceBuilder(unittest.TestCase):

    def _build(self, origin):
        builder = make_invoice_builder(origin)
        return builder(_doc(), [_line()], "HQ01")

    def test_documenteme_mantiene_punto_estandar(self):
        factura = self._build("documenteme")
        self.assertEqual(factura["puntofacturacion"], "estandar")
        self.assertEqual(factura["tipoFacturaDoc"], "Estándar")

    def test_collection_genera_ds_soporte(self):
        factura = self._build("collection")
        self.assertEqual(factura["puntofacturacion"], "DS SOPORTE")
        self.assertEqual(factura["tipoFacturaDoc"], "Estándar")

    def test_origen_desconocido_usa_estandar(self):
        self.assertEqual(self._build("otro")["puntofacturacion"], "estandar")


class TestBuildPayloadAdapter(unittest.TestCase):

    def _get_lines(self, purchase_order):
        return [_line()], ""

    def test_build_payload_default_documenteme(self):
        payload = build_payload(
            [_doc()], self._get_lines, lambda po: "HQ01"
        )
        self.assertEqual(payload[0]["puntofacturacion"], "estandar")
        self.assertEqual(payload[0]["tipoFacturaDoc"], "Estándar")

    def test_build_payload_con_builder_collection(self):
        payload = build_payload(
            [_doc()],
            self._get_lines,
            lambda po: "HQ01",
            build_invoice_fn=make_invoice_builder("collection"),
        )
        self.assertEqual(payload[0]["puntofacturacion"], "DS SOPORTE")
        self.assertEqual(payload[0]["tipoFacturaDoc"], "Estándar")


class TestApproveCollectionInvoicesAdapter(unittest.TestCase):

    NOW = "2026-08-12 10:00:00"

    def _callbacks(self):
        calls = {
            "sent": [],
            "persisted": [],
            "marked": [],
        }

        def get_docs_fn(doc_names):
            return [_doc(name=name) for name in doc_names]

        def get_lines_fn(doc):
            return [_line()], ""

        def get_headquarter_fn(purchase_order):
            return "HQ01"

        def po_exists_fn(purchase_order):
            return bool(purchase_order)

        def receipt_bank_fn(purchase_order):
            if not purchase_order:
                return []
            return [
                {"name": "REC-1", "amount": 50000, "date": "2026-07-01",
                 "qp_invoice": ""}
            ]

        def send_request_fn(endpoint_code, payload):
            calls["sent"].append((endpoint_code, payload))
            return (
                {"Result": 0, "invoices": [
                    {"doc_number": "BC1001", "error": ""}
                ]},
                200,
            )

        def parse_doc_numbers_fn(resp):
            return (resp or {}).get("invoices") or []

        def persist_invoice_fn(doc, doc_number, now):
            calls["persisted"].append(doc.get("nvfac_nume"))

        def mark_registered_fn(doc, doc_number):
            calls["marked"].append(doc.get("nvfac_nume"))

        def mark_error_fn(doc, error):
            calls["marked"].append((doc.get("nvfac_nume"), "error"))

        def commit_fn():
            pass

        return calls, {
            "get_docs_fn": get_docs_fn,
            "get_lines_fn": get_lines_fn,
            "get_headquarter_fn": get_headquarter_fn,
            "po_exists_fn": po_exists_fn,
            "receipt_bank_fn": receipt_bank_fn,
            "send_request_fn": send_request_fn,
            "parse_doc_numbers_fn": parse_doc_numbers_fn,
            "persist_invoice_fn": persist_invoice_fn,
            "mark_registered_fn": mark_registered_fn,
            "mark_error_fn": mark_error_fn,
            "commit_fn": commit_fn,
        }

    def test_payload_collection_envia_ds_soporte(self):
        calls, kwargs = self._callbacks()
        result = approve_collection_invoices(
            ["DOC1"], now=self.NOW, **kwargs
        )

        self.assertEqual(result["approved"][0]["doc_number"], "BC1001")
        self.assertEqual(len(calls["sent"]), 1)
        _endpoint, payload = calls["sent"][0]
        self.assertEqual(payload[0]["puntofacturacion"], "DS SOPORTE")
        self.assertEqual(payload[0]["tipoFacturaDoc"], "Estándar")
        self.assertEqual(payload[0]["vendorNumber"], "050633410")


if __name__ == "__main__":
    unittest.main()