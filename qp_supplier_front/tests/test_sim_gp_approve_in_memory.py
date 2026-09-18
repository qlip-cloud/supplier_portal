# -*- coding: utf-8 -*-
"""
test_sim_gp_approve_in_memory.py
================================
Aprobacion documenteme simulada 100% en memoria con backend GP: con el flag
documenteme_simulation activo y backend="GP", approve_documents_core usa el
builder GP (noFacturaProveedor), el sender simulado GP y persiste en memoria
el qp_sync_flow="GP", completando BCC -> A via el actor de confirmacion simulado.

Ejecutar con: python -m unittest qp_supplier_front.tests.test_sim_gp_approve_in_memory -v
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
    store.insert("qp_SP_Supplier", {
        "name": SIM_NIT, "tax_id": SIM_NIT,
        "qp_is_service_supplier": 0,
    })
    store.insert("qp_SP_ItemHomologation", {
        "name": "{}:ITEM-2".format(SIM_NIT),
        "supplier": SIM_NIT,
        "supplier_item_code": "ITEM-2",
        "bc_item_code": "BC-ITEM-2",
        "active": 1,
    })
    store.insert("qp_SP_DetailLine", {
        "parent": name, "nvpro_codi": "ITEM-2", "nvdet_tcan": 2,
        "nvdet_valo": 400000, "nvdet_stot": total,
    })


class TestSimGpApproveInMemory(unittest.TestCase):

    def setUp(self):
        session.reset()
        self.store = MemoryStore()
        self.addCleanup(session.reset)

    def _run(self, doc_names):
        with patch.object(_approve_base.runtime, "is_simulation_enabled",
                          return_value=True), \
             patch.object(_approve_base, "frappe", MagicMock()):
            return _approve_base.approve_documents_core(
                doc_names, backend="GP"
            )

    def test_aprobacion_gp_simulada_llega_a_aprobado(self):
        _seed_cash(self.store)
        with patch("qp_supplier_front.simulation.session.store",
                   return_value=self.store):
            result = self._run(["999999999:F2"])

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(result["errors"], [])

        row = self.store.get("qp_SP_DocumentDetail", "999999999:F2")
        self.assertEqual(row["nvfac_esta"], "A")

        inv = self.store.query("qp_SP_PurchaseInvoice")
        self.assertEqual(len(inv), 1)
        self.assertEqual(inv[0]["qp_sync_flow"], "GP")
        # doc_number simulado GP: SIM{noFacturaProveedor}
        self.assertEqual(inv[0]["invoice_id"], "SIMSIM-FAC-0002")
        # Confirmacion sim reutiliza el enlace BC in-memory (igual que real).
        self.assertEqual(len(self.store.query("qp_SP_PurchaseInvoiceBC")), 1)


if __name__ == "__main__":
    unittest.main()