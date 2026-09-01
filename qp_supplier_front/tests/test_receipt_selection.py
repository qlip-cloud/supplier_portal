# -*- coding: utf-8 -*-
"""
test_receipt_selection.py
=========================
Pruebas unitarias para uses_cases/documenteme/receipt_selection.py
(seleccion manual del banco de recepciones).

Nucleo puro: no requiere Frappe ni base de datos.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_receipt_selection.py -v
"""
import unittest

from qp_supplier_front.uses_cases.documenteme.receipt_selection import (
    DEFINITIVE_STATES,
    classify_selection,
    is_definitive,
    select_claim_release,
    sum_selected,
    validate_apply,
)


def _receipt(name, amount, qp_invoice=None):
    return {"name": name, "amount": amount, "date": "2026-01-01",
            "qp_invoice": qp_invoice}


def _doc(nvfac_nume="FAC1", nvfac_stot=100, nvfac_esta="E"):
    return {"name": "DOC1", "nvfac_nume": nvfac_nume,
            "nvfac_stot": nvfac_stot, "nvfac_esta": nvfac_esta}


class TestClassifySelection(unittest.TestCase):

    def test_parcial(self):
        self.assertEqual(classify_selection(100, 40, 0.01), "parcial")

    def test_completo_exacto(self):
        self.assertEqual(classify_selection(100, 100, 0.01), "completo")

    def test_completo_dentro_de_epsilon(self):
        self.assertEqual(classify_selection(100, 100.005, 0.01), "completo")

    def test_excede(self):
        self.assertEqual(classify_selection(100, 140, 0.01), "excede")

    def test_excede_fuera_de_epsilon(self):
        self.assertEqual(classify_selection(100, 100.02, 0.01), "excede")

    def test_zero_vs_cero_completo(self):
        self.assertEqual(classify_selection(0, 0, 0.01), "completo")


class TestIsDefinitive(unittest.TestCase):

    def test_estados_definitivos(self):
        for status in DEFINITIVE_STATES:
            self.assertTrue(is_definitive(status))

    def test_estados_no_definitivos(self):
        for status in ("E", "V", "T"):
            self.assertFalse(is_definitive(status))


class TestSumSelected(unittest.TestCase):

    def test_suma_por_nombre(self):
        bank = [
            _receipt("R1", 40),
            _receipt("R2", 60),
            _receipt("R3", 200),
        ]
        self.assertEqual(sum_selected(bank, ["R1", "R2"]), 100.0)
        self.assertEqual(sum_selected(bank, ["R3"]), 200.0)

    def test_ignora_nombres_faltantes(self):
        self.assertEqual(sum_selected([_receipt("R1", 40)], ["R9"]), 0.0)

    def test_banco_vacio(self):
        self.assertEqual(sum_selected([], ["R1"]), 0.0)


class TestSelectClaimRelease(unittest.TestCase):

    def test_nuevo_y_liberado(self):
        to_claim, to_release = select_claim_release(
            ["R1", "R2"], ["R2", "R3"])
        self.assertEqual(to_claim, ["R3"])
        self.assertEqual(to_release, ["R1"])

    def test_sin_cambios(self):
        to_claim, to_release = select_claim_release(["R1"], ["R1"])
        self.assertEqual(to_claim, [])
        self.assertEqual(to_release, [])

    def test_sin_previos_y_vacio(self):
        to_claim, to_release = select_claim_release([], [])
        self.assertEqual(to_claim, [])
        self.assertEqual(to_release, [])

    def test_ordinal(self):
        to_claim, to_release = select_claim_release(
            ["R1", "R2"], ["R2", "R2", "R3"])
        self.assertEqual(to_claim, ["R3"])
        self.assertEqual(to_release, ["R1"])


class TestValidateApply(unittest.TestCase):

    def test_parcial_ok(self):
        bank = [_receipt("R1", 40), _receipt("R2", 60), _receipt("R3", 10)]
        ok, error, classification = validate_apply(
            _doc(), ["R1"], bank, 0.01)
        self.assertTrue(ok)
        self.assertEqual(classification, "parcial")

    def test_completo_ok(self):
        bank = [_receipt("R1", 40), _receipt("R2", 60)]
        ok, error, classification = validate_apply(
            _doc(), ["R1", "R2"], bank, 0.01)
        self.assertTrue(ok)
        self.assertEqual(classification, "completo")

    def test_excede_bloquea(self):
        bank = [_receipt("R1", 140)]
        ok, error, classification = validate_apply(
            _doc(), ["R1"], bank, 0.01)
        self.assertFalse(ok)
        self.assertEqual(classification, "excede")
        self.assertIn("excede", error)

    def test_estado_definitivo_bloquea(self):
        bank = [_receipt("R1", 40)]
        doc = _doc(nvfac_esta="BCC")
        ok, error, _ = validate_apply(doc, ["R1"], bank, 0.01)
        self.assertFalse(ok)
        self.assertIn("definitivo", error)

    def test_sin_seleccion_bloquea(self):
        ok, error, classification = validate_apply(_doc(), [], [], 0.01)
        self.assertFalse(ok)
        self.assertIsNone(classification)
        self.assertIn("Seleccione al menos un recibo", error)

    def test_recibo_reclamado_por_otra_factura_no_disponible(self):
        bank = [_receipt("R1", 40, qp_invoice="OTHER_FAC")]
        ok, error, _ = validate_apply(_doc(), ["R1"], bank, 0.01)
        self.assertFalse(ok)
        self.assertIn("no están disponibles", error)

    def test_recibo_reclamado_por_esta_factura_disponible(self):
        doc = _doc(nvfac_nume="FAC1")
        bank = [_receipt("R1", 100, qp_invoice="FAC1")]
        ok, error, classification = validate_apply(
            doc, ["R1"], bank, 0.01)
        self.assertTrue(ok)
        self.assertEqual(classification, "completo")


if __name__ == "__main__":
    unittest.main()