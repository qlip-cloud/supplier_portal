# -*- coding: utf-8 -*-
"""
test_selection_violations.py
============================
Pruebas del nucleo puro de violaciones de la regla de SELECCION manual de
recepciones (collect_selection_violations) para facturas de credito.

Nucleo puro: no requiere Frappe ni base de datos.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_selection_violations.py -v
"""
import unittest

from qp_supplier_front.uses_cases.documenteme.approve import (
    collect_selection_violations,
)


def _doc(**overrides):
    data = {
        "name": "DOC1",
        "nvfac_nume": "FAC001",
        "nvfac_orde": "PO1",
        "nvfac_esta": "E",
        "nvfac_conv": "2",
        "nvtip_docu": "F",
        "nvfac_stot": 100,
    }
    data.update(overrides)
    return data


def _receipt(name, amount, qp_invoice=None):
    return {"name": name, "amount": amount, "date": "2026-01-01",
            "qp_invoice": qp_invoice}


def _collect(docs, bank, count=1):
    return collect_selection_violations(
        docs,
        po_exists_fn=lambda po: True,
        receipt_bank_fn=lambda po: bank,
        oc_invoice_count_fn=lambda po: count,
    )


class TestSelectionViolations(unittest.TestCase):

    def test_sin_aplicar_bloquea(self):
        violations = _collect([_doc()], [_receipt("R1", 40), _receipt("R2", 60)],
                              count=2)
        self.assertEqual(len(violations), 1)
        self.assertTrue(violations[0]["blocking"])
        self.assertIn("seleccionar y aplicar", violations[0]["violations"][0])

    def test_relajado_completo_sin_violacion(self):
        violations = _collect([_doc()], [_receipt("R1", 100)], count=1)
        self.assertEqual(violations, [])

    def test_relajado_parcial_advertencia_forceable(self):
        violations = _collect([_doc()], [_receipt("R1", 40)], count=1)
        self.assertEqual(len(violations), 1)
        self.assertFalse(violations[0]["blocking"])
        self.assertIn("excede el valor de las recepciones",
                      violations[0]["violations"][0])

    def test_relajado_excede_advertencia_forceable(self):
        violations = _collect([_doc()], [_receipt("R1", 140)], count=1)
        self.assertEqual(len(violations), 1)
        self.assertFalse(violations[0]["blocking"])
        self.assertIn("excede el total", violations[0]["violations"][0])

    def test_aplicado_completo_sin_violacion(self):
        bank = [_receipt("R1", 100, qp_invoice="FAC001")]
        violations = _collect([_doc()], bank, count=1)
        self.assertEqual(violations, [])

    def test_aplicado_parcial_advertencia_forceable(self):
        bank = [_receipt("R1", 40, qp_invoice="FAC001")]
        violations = _collect([_doc()], bank, count=1)
        self.assertEqual(len(violations), 1)
        self.assertFalse(violations[0]["blocking"])

    def test_aplicado_excede_advertencia_forceable(self):
        bank = [_receipt("R1", 140, qp_invoice="FAC001")]
        violations = _collect([_doc()], bank, count=1)
        self.assertEqual(len(violations), 1)
        self.assertFalse(violations[0]["blocking"])

    def test_sin_recepciones_en_la_oc_advertencia_forceable(self):
        violations = _collect([_doc()], [], count=1)
        self.assertEqual(len(violations), 1)
        self.assertFalse(violations[0]["blocking"])
        self.assertIn("No se encontraron recepciones", violations[0]["violations"][0])

    def test_contado_y_nota_credito_se_omiten(self):
        cash = _doc(nvfac_conv="1")
        note = _doc(nvtip_docu="C")
        bank = [_receipt("R1", 40)]
        violations = _collect([cash, note], bank, count=2)
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
