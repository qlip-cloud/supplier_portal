# -*- coding: utf-8 -*-
"""
test_devolution_bank.py
=======================
Pruebas del nucleo puro "banco de devoluciones" de las NC tipo 5 GP
(uses_cases/documenteme/devolution_bank.py).

Cubre:
- build_receipt_bank / build_po_bank (construccion del banco por linea).
- apply_consumed (resta lo ya devuelto por linea).
- allocate_devolution (asignacion greedy y deteccion de excedente).
- excess_message (alerta descriptiva).

Ejecutar con: python -m unittest qp_supplier_front.tests.test_devolution_bank -v
"""
import unittest

from qp_supplier_front.uses_cases.documenteme.devolution_bank import (
    allocate_devolution,
    apply_consumed,
    build_po_bank,
    build_receipt_bank,
    excess_message,
)


class TestBuildBank(unittest.TestCase):

    def test_receipt_bank_preserva_lineas_de_recepcion(self):
        items = [
            {"item_code": "A", "qty": 2, "receiving_no": "R1", "order_no": "PO1"},
            {"item_code": "A", "qty": 3, "receiving_no": "R2", "order_no": "PO1"},
            {"item_code": "B", "qty": 1, "receiving_no": "R1", "order_no": "PO1"},
        ]
        bank = build_receipt_bank(items)
        self.assertEqual(len(bank), 3)
        self.assertEqual(bank[0]["receiving_no"], "R1")
        self.assertEqual(bank[1]["qty"], 3)

    def test_receipt_bank_ignora_sin_codigo_o_sin_cantidad(self):
        bank = build_receipt_bank([
            {"item_code": None, "qty": 5, "receiving_no": "R1", "order_no": "PO1"},
            {"item_code": "A", "qty": 0, "receiving_no": "R1", "order_no": "PO1"},
        ])
        self.assertEqual(bank, [])

    def test_po_bank_sin_recepcion(self):
        bank = build_po_bank([{"item_code": "B", "qty": 5, "idx": 3}],
                             order_no="PO9")
        self.assertEqual(len(bank), 1)
        self.assertEqual(bank[0]["receiving_no"], "")
        self.assertEqual(bank[0]["order_no"], "PO9")
        self.assertEqual(bank[0]["idx"], 3)

    def test_po_bank_propaga_idx_a_la_asignacion(self):
        bank = build_po_bank([{"item_code": "B", "qty": 5, "idx": 3}],
                             order_no="PO9")
        assigned, excess = allocate_devolution(
            [{"item_code": "B", "qty": 2}], apply_consumed(bank, [])
        )
        self.assertEqual(excess, [])
        self.assertEqual(assigned[0]["idx"], 3)
        self.assertEqual(assigned[0]["order_no"], "PO9")


class TestApplyConsumed(unittest.TestCase):

    def test_resta_lo_devuelto_por_linea(self):
        bank = build_receipt_bank([
            {"item_code": "A", "qty": 2, "receiving_no": "R1", "order_no": "PO1"},
            {"item_code": "A", "qty": 3, "receiving_no": "R2", "order_no": "PO1"},
        ])
        consumed = [
            {"item_code": "A", "qty": 1, "receiving_no": "R1", "order_no": "PO1"},
        ]
        available = apply_consumed(bank, consumed)
        self.assertEqual(available[0]["qty"], 1)
        self.assertEqual(available[1]["qty"], 3)

    def test_nunca_baja_de_cero(self):
        bank = build_po_bank([{"item_code": "B", "qty": 2}], order_no="PO1")
        consumed = [{"item_code": "B", "qty": 5, "receiving_no": "", "order_no": "PO1"}]
        available = apply_consumed(bank, consumed)
        self.assertEqual(available[0]["qty"], 0)


class TestAllocateDevolution(unittest.TestCase):

    def test_devuelve_una_linea_toma_de_la_primera_recepcion(self):
        bank = build_receipt_bank([
            {"item_code": "A", "qty": 2, "receiving_no": "R1", "order_no": "PO1"},
            {"item_code": "A", "qty": 3, "receiving_no": "R2", "order_no": "PO1"},
        ])
        assigned, excess = allocate_devolution(
            [{"item_code": "A", "qty": 1}], apply_consumed(bank, [])
        )
        self.assertEqual(excess, [])
        self.assertEqual(assigned, [
            {"item_code": "A", "qty": 1, "idx": 0,
             "receiving_no": "R1", "order_no": "PO1"},
        ])

    def test_divide_devolucion_entre_varias_recepciones(self):
        bank = build_receipt_bank([
            {"item_code": "A", "qty": 2, "receiving_no": "R1", "order_no": "PO1"},
            {"item_code": "A", "qty": 3, "receiving_no": "R2", "order_no": "PO1"},
        ])
        consumed = [
            {"item_code": "A", "qty": 1, "receiving_no": "R1", "order_no": "PO1"},
        ]
        assigned, excess = allocate_devolution(
            [{"item_code": "A", "qty": 2}], apply_consumed(bank, consumed)
        )
        self.assertEqual(excess, [])
        self.assertEqual(len(assigned), 2)
        self.assertEqual(assigned[0]["receiving_no"], "R1")
        self.assertEqual(assigned[0]["qty"], 1)
        self.assertEqual(assigned[1]["receiving_no"], "R2")
        self.assertEqual(assigned[1]["qty"], 1)

    def test_excede_el_banco(self):
        bank = build_receipt_bank([
            {"item_code": "A", "qty": 2, "receiving_no": "R1", "order_no": "PO1"},
        ])
        consumed = [
            {"item_code": "A", "qty": 2, "receiving_no": "R1", "order_no": "PO1"},
        ]
        assigned, excess = allocate_devolution(
            [{"item_code": "A", "qty": 2}], apply_consumed(bank, consumed)
        )
        self.assertEqual(assigned, [])
        self.assertEqual(len(excess), 1)
        self.assertEqual(excess[0]["item_code"], "A")
        self.assertEqual(excess[0]["qty"], 2)

    def test_multiple_productos_exceso_por_producto(self):
        bank = build_po_bank(
            [{"item_code": "B", "qty": 1}, {"item_code": "C", "qty": 1}],
            order_no="PO9",
        )
        assigned, excess = allocate_devolution(
            [{"item_code": "B", "qty": 2}, {"item_code": "C", "qty": 1}],
            apply_consumed(bank, []),
        )
        # B asigna 1 (y excede 1), C asigna 1.
        self.assertEqual(len(assigned), 2)
        self.assertEqual(len(excess), 1)
        self.assertEqual(excess[0]["item_code"], "B")

    def test_excess_message(self):
        message = excess_message([{"item_code": "A", "qty": 2}])
        self.assertIn("excede", message)
        self.assertIn("A", message)
        self.assertEqual(excess_message([]), "")


if __name__ == "__main__":
    unittest.main()