# -*- coding: utf-8 -*-
"""
test_sim_approve_in_memory.py
=============================
Aprobacion simulada 100% en memoria: con el flag activo, approve_documents_core
usa callbacks memory (get_docs/persist/mark/refs) sobre el store de la sesion;
contado llega a "A" y credito sin OC queda en error (sin tocar DB real).

Ejecutar con: python -m pytest qp_supplier_front/tests/test_sim_approve_in_memory.py -v
"""
import unittest
from unittest.mock import MagicMock, patch

from qp_supplier_front.resources.documenteme import _approve_base
from qp_supplier_front.simulation import session
from qp_supplier_front.simulation.store import MemoryStore

SIM_NIT = "999999999"


def _seed_cash(store, name="999999999:F2", nume="SIM-FAC-0002", total=800000):
    store.insert("qp_SP_DocumentDetail", {
        "name": name, "nvfac_nume": nume, "nvpro_ndoc": SIM_NIT,
        "nvfac_fech": "2026-08-25", "nvfac_cufe": "CUFE2",
        "nvtip_docu": "FAC", "nvfac_fpag": "", "nvfac_orde": "",
        "nvfac_rece": "", "nvfac_totp": total, "nvfac_esta": "V",
        "nvfac_ueve": "", "nvfac_conv": "1", "nvmon_codi": "COP",
        "nvfac_stot": total, "nvfac_viva": 0, "nvpro_nomb": "PROVEEDOR SIM",
    })
    store.insert("qp_SP_DetailLine", {
        "parent": name, "nvpro_codi": "ITEM-2", "nvdet_tcan": 2,
        "nvdet_valo": 400000, "nvdet_stot": total,
    })


def _seed_credit(store, name="999999999:F1", nume="SIM-FAC-0001", total=1500000):
    store.insert("qp_SP_DocumentDetail", {
        "name": name, "nvfac_nume": nume, "nvpro_ndoc": SIM_NIT,
        "nvfac_fech": "2026-08-25", "nvfac_cufe": "CUFE1",
        "nvtip_docu": "FAC", "nvfac_fpag": "", "nvfac_orde": "PO-SIM-0001",
        "nvfac_rece": "", "nvfac_totp": total, "nvfac_esta": "V",
        "nvfac_ueve": "", "nvfac_conv": "2", "nvmon_codi": "COP",
        "nvfac_stot": total, "nvfac_viva": 0, "nvpro_nomb": "PROVEEDOR SIM",
    })
    store.insert("qp_SP_DetailLine", {
        "parent": name, "nvpro_codi": "ITEM-1", "nvdet_tcan": 10,
        "nvdet_valo": 150000, "nvdet_stot": total,
    })


class TestSimApproveInMemory(unittest.TestCase):

    def setUp(self):
        session.reset()
        self.store = MemoryStore()
        self.addCleanup(session.reset)

    def _run(self, doc_names):
        with patch.object(_approve_base.runtime, "is_simulation_enabled",
                          return_value=True), \
             patch.object(_approve_base, "frappe", MagicMock()):
            return _approve_base.approve_documents_core(doc_names)

    def test_contado_llega_a_aprobado(self):
        _seed_cash(self.store)
        with patch("qp_supplier_front.simulation.session.store",
                   return_value=self.store):
            self._run(["999999999:F2"])

        row = self.store.get("qp_SP_DocumentDetail", "999999999:F2")
        self.assertEqual(row["nvfac_esta"], "A")
        self.assertTrue(self.store.exists("qp_SP_PurchaseInvoice", "999999999:F2"))
        inv = self.store.query("qp_SP_PurchaseInvoice")
        self.assertEqual(inv[0]["invoice_id"], "SIMSIM-FAC-0002")
        bc = self.store.query("qp_SP_PurchaseInvoiceBC")
        self.assertEqual(len(bc), 1)

    def test_credito_sin_oc_queda_en_error(self):
        _seed_credit(self.store)
        with patch("qp_supplier_front.simulation.session.store",
                   return_value=self.store):
            result = self._run(["999999999:F1"])

        self.assertEqual(result["approved"], [])
        self.assertEqual(len(result["errors"]), 1)
        row = self.store.get("qp_SP_DocumentDetail", "999999999:F1")
        self.assertNotEqual(row["nvfac_esta"], "A")


if __name__ == "__main__":
    unittest.main()