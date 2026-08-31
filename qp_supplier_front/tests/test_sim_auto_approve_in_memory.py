# -*- coding: utf-8 -*-
"""
test_sim_auto_approve_in_memory.py
==================================
Auto-aprobacion simulada en memoria (flujo automatico E -> V -> BCC -> A) con
run_auto_approve: promote_eligible_to_v, get_v_doc_names y approve_documents_core
operan sobre el store de la sesion; sin tocar la DB real.

Ejecutar con: python -m pytest qp_supplier_front/tests/test_sim_auto_approve_in_memory.py -v
"""
import unittest
from unittest.mock import MagicMock, patch

from qp_supplier_front.resources.documenteme import auto_approve as arapp
from qp_supplier_front.resources.documenteme import _approve_base as abase
from qp_supplier_front.simulation import session
from qp_supplier_front.simulation.store import MemoryStore

SIM_NIT = "999999999"


def _seed(store, estado="E"):
    store.insert("qp_SP_DocumentDetail", {
        "name": "999999999:F2", "nvfac_nume": "SIM-FAC-0002",
        "nvpro_ndoc": SIM_NIT, "nvfac_fech": "2026-08-25",
        "nvfac_cufe": "CUFE2", "nvtip_docu": "FAC", "nvfac_fpag": "",
        "nvfac_orde": "", "nvfac_rece": "", "nvfac_totp": 800000,
        "nvfac_esta": estado, "nvfac_ueve": "", "nvfac_conv": "1",
        "nvmon_codi": "COP", "nvfac_stot": 800000, "nvfac_viva": 0,
        "nvpro_nomb": "PROVEEDOR SIM",
    })
    store.insert("qp_SP_DetailLine", {
        "parent": "999999999:F2", "nvpro_codi": "ITEM-2", "nvdet_tcan": 2,
        "nvdet_valo": 400000, "nvdet_stot": 800000,
    })
    store.insert("qp_SP_MasterSetup", {"auto_approve": 1})


class TestSimAutoApproveInMemory(unittest.TestCase):

    def setUp(self):
        session.reset()
        self.store = MemoryStore()
        self.addCleanup(session.reset)

    def _patched(self):
        return [
            patch.object(arapp.runtime, "is_simulation_enabled",
                         return_value=True),
            patch.object(arapp, "frappe", MagicMock()),
            patch.object(abase, "frappe", MagicMock()),
        ]

    def test_auto_aprueba_contado_has_a(self):
        _seed(self.store)
        with patch("qp_supplier_front.simulation.session.store",
                   return_value=self.store):
            for p in self._patched():
                p.start()
                self.addCleanup(p.stop)

            result = arapp.run_auto_approve(enqueue=False)

        self.assertFalse(result["skipped"])
        self.assertIn("SIM-FAC-0002", result["promoted"])
        row = self.store.get("qp_SP_DocumentDetail", "999999999:F2")
        self.assertEqual(row["nvfac_esta"], "A")
        self.assertTrue(self.store.exists("qp_SP_PurchaseInvoice", "999999999:F2"))
        self.assertTrue(self.store.exists("qp_SP_PurchaseInvoiceBC", "SIMSIM-FAC-0002"))


if __name__ == "__main__":
    unittest.main()