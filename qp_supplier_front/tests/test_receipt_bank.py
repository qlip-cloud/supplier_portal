# -*- coding: utf-8 -*-
"""
test_receipt_bank.py
====================
Pruebas unitarias para uses_cases/documenteme/receipt_bank.py.

Nucleo puro: no requiere Frappe ni base de datos.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_receipt_bank.py -v
"""
import unittest

from qp_supplier_front.uses_cases.documenteme.receipt_bank import (
    DEFAULT_EPSILON,
    are_close,
    pack_oc_group,
    solve_receipt_bank,
    unconsumed_receipts,
)


def _receipt(name, amount, date="2026-01-01", qp_invoice=None):
    return {"name": name, "amount": amount, "date": date, "qp_invoice": qp_invoice}


def _invoice(name, total):
    return {"nvfac_nume": name, "nvfac_stot": total}


class TestAreClose(unittest.TestCase):

    def test_iguales(self):
        self.assertTrue(are_close(100, 100, 0.0))

    def test_dentro_de_epsilon(self):
        self.assertTrue(are_close(100, 100.005, 0.01))

    def test_fuera_de_epsilon(self):
        self.assertFalse(are_close(100, 100.02, 0.01))

    def test_none_se_trata_como_cero(self):
        self.assertTrue(are_close(None, 0, 0.0))

    def test_valores_invalidos_se_tratan_como_cero(self):
        self.assertTrue(are_close("abc", 0, 0.0))


class TestUnconsumedReceipts(unittest.TestCase):

    def test_filtra_consumidas(self):
        receipts = [
            _receipt("R1", 100, qp_invoice=None),
            _receipt("R2", 200, qp_invoice="FAC001"),
            _receipt("R3", 300, qp_invoice=""),
            _receipt("R4", 400),
        ]
        self.assertEqual(
            [r["name"] for r in unconsumed_receipts(receipts)],
            ["R1", "R3", "R4"],
        )

    def test_sin_recepciones(self):
        self.assertEqual(unconsumed_receipts([]), [])
        self.assertEqual(unconsumed_receipts(None), [])


class TestSolveReceiptBank(unittest.TestCase):

    def test_sin_recepciones_retorna_none(self):
        self.assertIsNone(solve_receipt_bank(100, [], DEFAULT_EPSILON))

    def test_sin_orden_de_recepciones_no_consumidas(self):
        receipts = [_receipt("R1", 100, qp_invoice="FAC001")]
        self.assertIsNone(solve_receipt_bank(100, receipts, DEFAULT_EPSILON))

    def test_nivel1_acumulacion_cronologica(self):
        receipts = [
            _receipt("R1", 50, date="2026-01-01"),
            _receipt("R2", 50, date="2026-01-02"),
        ]
        matched = solve_receipt_bank(100, receipts, DEFAULT_EPSILON)
        self.assertEqual([r["name"] for r in matched], ["R1", "R2"])

    def test_nivel2_subset_dfs_cuando_cronologico_falla(self):
        receipts = [
            _receipt("R1", 50, date="2026-01-01"),
            _receipt("R2", 60, date="2026-01-02"),
            _receipt("R3", 40, date="2026-01-03"),
        ]
        matched = solve_receipt_bank(100, receipts, DEFAULT_EPSILON)
        self.assertEqual([r["name"] for r in matched], ["R2", "R3"])

    def test_ignora_recepciones_consumidas(self):
        receipts = [
            _receipt("R1", 100, qp_invoice="FAC001"),
            _receipt("R2", 100),
        ]
        matched = solve_receipt_bank(100, receipts, DEFAULT_EPSILON)
        self.assertEqual([r["name"] for r in matched], ["R2"])

    def test_sin_combinacion_exacta_retorna_none(self):
        receipts = [
            _receipt("R1", 40, date="2026-01-01"),
            _receipt("R2", 40, date="2026-01-02"),
        ]
        self.assertIsNone(solve_receipt_bank(100, receipts, DEFAULT_EPSILON))

    def test_epsilon_permite_aproximacion(self):
        receipts = [_receipt("R1", 100)]
        self.assertIsNotNone(solve_receipt_bank(100.005, receipts, 0.01))
        self.assertIsNone(solve_receipt_bank(100.02, receipts, 0.01))


class TestPackOCGroup(unittest.TestCase):

    def test_grupo_vacio(self):
        self.assertEqual(pack_oc_group([], [], 0.01, 4, 8), {})

    def test_sin_recepciones(self):
        self.assertEqual(pack_oc_group([_invoice("A", 100)], [], 0.01, 4, 8), {})

    def test_grupo_sin_coincidencias_retorna_vacio(self):
        receipts = [
            _receipt("R0", 10, date="2026-01-01"),
            _receipt("R1", 20, date="2026-01-02"),
        ]
        self.assertEqual(
            pack_oc_group([_invoice("A", 999), _invoice("B", 888)],
                          receipts, 0.01, 4, 8),
            {},
        )

    def test_asignacion_simple(self):
        receipts = [_receipt("R1", 100)]
        packed = pack_oc_group([_invoice("A", 100)], receipts, 0.01, 4, 8)
        self.assertEqual([r["name"] for r in packed["A"]], ["R1"])

    def test_b2_emparejamiento_ambiguo_maximiza_completadas(self):
        receipts = [
            _receipt("R0", 10, date="2026-01-01"),
            _receipt("R1", 30, date="2026-01-02"),
            _receipt("R2", 40, date="2026-01-03"),
        ]
        invoices = [_invoice("A", 40), _invoice("B", 30)]
        packed = pack_oc_group(invoices, receipts, 0.01, 4, 8)
        self.assertEqual([r["name"] for r in packed["A"]], ["R2"])
        self.assertEqual([r["name"] for r in packed["B"]], ["R1"])

    def test_b3_factura_incompleta_no_consume(self):
        receipts = [
            _receipt("R0", 20, date="2026-01-01"),
            _receipt("R1", 30, date="2026-01-02"),
        ]
        invoices = [_invoice("A", 100), _invoice("B", 50)]
        packed = pack_oc_group(invoices, receipts, 0.01, 4, 8)
        self.assertNotIn("A", packed)
        self.assertEqual([r["name"] for r in packed["B"]], ["R0", "R1"])

    def test_ignora_recepciones_consumidas(self):
        receipts = [
            _receipt("R1", 50, qp_invoice="FAC001"),
            _receipt("R2", 50),
        ]
        packed = pack_oc_group([_invoice("A", 50)], receipts, 0.01, 4, 8)
        self.assertEqual([r["name"] for r in packed["A"]], ["R2"])

    def test_degrada_a_greedy_cuando_grupo_excede_max_invoices(self):
        receipts = [
            _receipt("R0", 10, date="2026-01-01"),
            _receipt("R1", 20, date="2026-01-02"),
            _receipt("R2", 30, date="2026-01-03"),
        ]
        invoices = [
            _invoice("A", 10),
            _invoice("B", 20),
            _invoice("C", 30),
        ]
        packed = pack_oc_group(invoices, receipts, 0.01, 2, 8)
        self.assertEqual([r["name"] for r in packed["A"]], ["R0"])
        self.assertEqual([r["name"] for r in packed["B"]], ["R1"])
        self.assertEqual([r["name"] for r in packed["C"]], ["R2"])


if __name__ == "__main__":
    unittest.main()
