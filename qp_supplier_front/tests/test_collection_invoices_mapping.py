# -*- coding: utf-8 -*-
"""
tests/test_collection_invoices_mapping.py
=========================================
Tests puros del nucleo de facturas de cuentas de cobro (mapping, linea BC y
validacion adaptada). Sin Frappe ni base de datos.
"""
import unittest

from qp_supplier_front.uses_cases.collection_invoices.mapping import (
    build_document_dict,
    build_single_line,
    collect_validation_violations,
    evaluate_document,
)


class TestBuildDocumentDict(unittest.TestCase):

    def test_mapea_filas_de_purchase_invoice(self):
        row = {
            "name": "PI-1",
            "qp_status": "V",
            "nvfac_fech": "2026-09-01",
            "nvpro_ndoc": "999999999",
            "nvfac_nume": "PI-1",
            "nvfac_cufe": "CUFE-1",
            "nvfac_conv": "2",
            "subtotal": 600000,
            "tax": 0,
            "total": 600000,
            "currency": "COP",
            "purchase_order_id": "PO-CA-0001",
            "collection_account": "CA-SIM-0001",
        }
        doc = build_document_dict(row)

        self.assertEqual(doc["name"], "PI-1")
        self.assertEqual(doc["nvfac_nume"], "PI-1")
        self.assertEqual(doc["nvpro_ndoc"], "999999999")
        self.assertEqual(doc["nvfac_orde"], "PO-CA-0001")
        self.assertEqual(doc["nvfac_stot"], 600000)
        self.assertEqual(doc["nvfac_totp"], 600000)
        self.assertEqual(doc["nvfac_conv"], "2")
        self.assertEqual(doc["nvfac_esta"], "V")
        self.assertEqual(doc["nvmon_codi"], "COP")
        self.assertEqual(doc["collection_account"], "CA-SIM-0001")

    def test_defaults_cuando_faltan_campos(self):
        doc = build_document_dict({"name": "PI-1"})
        self.assertEqual(doc["nvfac_nume"], "PI-1")
        self.assertEqual(doc["nvfac_conv"], "1")
        self.assertEqual(doc["nvfac_esta"], "E")
        self.assertEqual(doc["nvmon_codi"], "COP")

    def test_none_devuelve_dict_con_name_nulo(self):
        doc = build_document_dict(None)
        self.assertIsNone(doc["name"])


class TestBuildSingleLine(unittest.TestCase):

    def test_usando_primer_item_y_monto_a_facturar(self):
        line = build_single_line(
            {"item_code": "ITEM-0001"},
            600000,
            order_no="PO-CA-0001",
        )
        self.assertEqual(line["item_code"], "ITEM-0001")
        self.assertEqual(line["qty"], 1)
        self.assertEqual(line["rate"], 600000)
        self.assertEqual(line["idx"], 0)
        self.assertEqual(line["receiving_no"], "")
        self.assertEqual(line["order_no"], "PO-CA-0001")

    def test_sin_item_devuelve_linea_vacia(self):
        line = build_single_line(None, 1000, order_no="")
        self.assertEqual(line["item_code"], "")
        self.assertEqual(line["rate"], 1000)


def _make_doc(total, po="PO-1", conv="2"):
    return {
        "name": "PI-{}".format(total),
        "nvfac_nume": "N-{}".format(total),
        "nvpro_ndoc": "999999999",
        "nvfac_fech": "2026-09-01",
        "nvfac_orde": po,
        "nvfac_stot": total,
        "nvfac_viva": 0,
        "nvfac_totp": total,
        "nvfac_conv": conv,
        "nvfac_esta": "E",
        "nvmon_codi": "COP",
    }


class TestValidation(unittest.TestCase):

    def test_cumple_regla_sin_violaciones(self):
        def po_exists(po):
            return po == "PO-1"

        def receipt_bank(po):
            if po != "PO-1":
                return []
            return [
                {"name": "REC-1", "amount": 400000, "date": "2026-08-01", "qp_invoice": ""},
                {"name": "REC-2", "amount": 200000, "date": "2026-08-02", "qp_invoice": ""},
            ]

        doc = _make_doc(600000, po="PO-1")
        ok, error = evaluate_document(doc, po_exists, receipt_bank)
        self.assertTrue(ok)
        self.assertEqual(error, "")

    def test_sin_orden_de_compra_falla(self):
        doc = _make_doc(600000, po="")
        ok, error = evaluate_document(doc, lambda po: False, lambda po: [])
        self.assertFalse(ok)
        self.assertIn("orden de compra", error)

    def test_recepciones_no_cubren_monto_falla(self):
        def po_exists(po):
            return po == "PO-1"

        def receipt_bank(po):
            return [
                {"name": "REC-1", "amount": 100000, "date": "2026-08-01", "qp_invoice": ""},
            ]

        doc = _make_doc(500000, po="PO-1")
        ok, error = evaluate_document(doc, po_exists, receipt_bank)
        self.assertFalse(ok)
        self.assertIn("No existe una combinación", error)

    def test_collect_validation_violations_acumula_por_factura(self):
        docs = [_make_doc(600000, po="PO-1"), _make_doc(500000, po="")]
        violations = collect_validation_violations(
            docs, lambda po: False, lambda po: []
        )
        self.assertEqual(len(violations), 2)
        self.assertEqual(violations[0]["nvfac_nume"], "N-600000")
        self.assertEqual(violations[1]["nvfac_nume"], "N-500000")

    def test_contado_sin_oc_ni_recibos_aprueba_sin_regla(self):
        """Cash: sin regla activa, no exige OC ni recibos -> registrable."""
        doc = _make_doc(600000, po="", conv="1")
        ok, error = evaluate_document(doc, lambda po: False, lambda po: [])
        self.assertTrue(ok)
        self.assertEqual(error, "")

    def test_contado_viola_regla_no_receipt(self):
        """Cash con regla no_receipt activa: exige recibos para registrarse."""
        def resolve_rule(doc):
            return {"rule_code": "no_receipt", "enabled": 1}

        doc = _make_doc(600000, po="PO-1", conv="1")
        # PO-1 existe pero no tiene recepciones -> viola la regla.
        ok, error = evaluate_document(
            doc,
            lambda po: po == "PO-1",
            lambda po: [],
            resolve_rule_fn=resolve_rule,
        )
        self.assertFalse(ok)
        self.assertIn("regla de rechazo", error)

    def test_contado_cumple_regla_no_receipt(self):
        def resolve_rule(doc):
            return {"rule_code": "no_receipt", "enabled": 1}

        doc = _make_doc(600000, po="PO-1", conv="1")
        ok, error = evaluate_document(
            doc,
            lambda po: po == "PO-1",
            lambda po: [
                {"name": "REC-1", "amount": 600000, "date": "2026-08-01", "qp_invoice": ""},
            ],
            resolve_rule_fn=resolve_rule,
        )
        self.assertTrue(ok)
        self.assertEqual(error, "")


if __name__ == "__main__":
    unittest.main()