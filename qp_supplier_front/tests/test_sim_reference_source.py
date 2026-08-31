# -*- coding: utf-8 -*-
"""
test_sim_reference_source.py
============================
Adaptador de referencias en memoria (MemoryReferenceSource): lee Purchase
Order / Purchase Receipt (+ child tables) de los seeds, con el mismo contrato
que la implementacion real (infrastructure/adapters/reference_source.py). Sin
base de datos real.

Ejecutar con: python -m unittest qp_supplier_front.tests.test_sim_reference_source -v
"""
import unittest

from qp_supplier_front.simulation import seeds
from qp_supplier_front.simulation.reference_source import MemoryReferenceSource
from qp_supplier_front.simulation.store import MemoryStore


class TestMemoryReferenceSource(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()
        seeds.seed_scenario(self.store)
        self.refs = MemoryReferenceSource(self.store)

    def test_po_exists_y_items(self):
        self.assertTrue(self.refs.po_exists("PO-A-0001"))
        self.assertFalse(self.refs.po_exists("PO-NO-EXISTE"))
        items = self.refs.po_items("PO-A-0001")
        self.assertEqual(
            [i["item_code"] for i in items], ["ITEM-POA1", "ITEM-POA2"])
        self.assertEqual(items[0]["qp_unit_cost"], 2000)

    def test_receipts_y_items_con_delivery_note(self):
        receipts = self.refs.receipts_for("PO-C-0001")
        self.assertEqual(
            [r["name"] for r in receipts], ["REC-C-1", "REC-C-2"])
        self.assertEqual(receipts[0]["supplier_delivery_note"], "RECIBO C1 · 500")
        items = self.refs.receipt_items_for(["REC-C-1", "REC-C-2"])
        self.assertEqual(
            [i["item_code"] for i in items], ["ITEM-REC-C1", "ITEM-REC-C2"])
        self.assertEqual(items[0]["amount"], 500)

    def test_receipt_bank_for(self):
        bank = self.refs.receipt_bank_for("PO-A-0001")
        self.assertEqual(
            [b["name"] for b in bank],
            ["REC-A-1", "REC-A-2", "REC-A-3", "REC-A-4"])
        self.assertEqual(bank[0]["amount"], 500)

    def test_receipts_for_filtra_por_qp_invoice(self):
        for name in ("REC-A-1", "REC-A-2"):
            self.store.set_value(
                "qp_SP_PurchaseReceipt", name, "qp_invoice", "SIM-POA-0001")
        assigned = self.refs.receipts_for("PO-A-0001", qp_invoice="SIM-POA-0001")
        self.assertEqual([r["name"] for r in assigned], ["REC-A-1", "REC-A-2"])
        self.assertEqual(
            self.refs.receipts_for("PO-A-0001", qp_invoice="SIM-POA-0002"), [])
        self.assertEqual(len(self.refs.receipts_for("PO-A-0001")), 4)

    def test_facade_expone_references_de_memoria(self):
        from qp_supplier_front.infrastructure.adapters.data_facade import DataFacade
        facade = DataFacade(store=self.store)
        self.assertTrue(facade.references.po_exists("PO-B-0001"))
        self.assertEqual(
            facade.references.receipt_bank_for("PO-A-0001")[0]["name"], "REC-A-1")


if __name__ == "__main__":
    unittest.main()