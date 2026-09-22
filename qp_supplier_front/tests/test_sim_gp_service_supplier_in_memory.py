# -*- coding: utf-8 -*-
"""
test_sim_gp_service_supplier_in_memory.py
=========================================
Proveedor de servicio (qp_is_service_supplier=1) en el flujo documenteme GP:
la OC y las recepciones NO son obligatorias, sin importar el default de
rechazo del MasterSetup.

- Sin regla de auto-rechazo en el proveedor: la factura de servicio sin OC
  ni recibo se aprueba automaticamente (E -> V -> BCC -> A) con backend GP,
  aunque el MasterSetup tenga una regla no_po que la rechazaria.
- Con regla no_po en el PROVEEDOR y sin OC: NO se promueve a "V" (no se
  aprueba) y la regla decide el rechazo.

Ejecutar con: python -m unittest qp_supplier_front.tests.test_sim_gp_service_supplier_in_memory -v
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()
sys.modules["frappe.model"] = MagicMock()
sys.modules["frappe.model.document"] = MagicMock()

from qp_supplier_front.resources.documenteme import (  # noqa: E402
    _approve_base as abase,
    auto_approve as arapp,
)
from qp_supplier_front.simulation import (  # noqa: E402
    seeds,
    session,
)
from qp_supplier_front.simulation.store import (  # noqa: E402
    MemoryStore,
)

SERVICE_NIT = seeds.GP_SIM_SERVICE_NIT
DOC_NAME = "{}:SRV-FAC-0001".format(SERVICE_NIT)
INVOICE_NUM = "SRV-FAC-0001"


def _seed_doc(store, supplier_rule=None, nvfac_conv="2", nvfac_orde=""):
    """Factura de proveedor servicio sin OC/recepcion (credito) + reglas."""
    seeds.seed_supplier(store, SERVICE_NIT,
                        qp_is_service_supplier=True,
                        auto_reject=supplier_rule)
    seeds.seed_reject_rule(store, "RULE-NO-PO", "no_po",
                           motive="Rechazo: falta OC")
    # Default global exigiria no_po: para servicios NO debe aplicar.
    seeds.seed_master_setup(store, auto_approve=1,
                            auto_reject="RULE-NO-PO",
                            documenteme_backend="GP")
    store.insert("qp_SP_DocumentDetail", {
        "name": DOC_NAME,
        "nvfac_nume": INVOICE_NUM,
        "nvpro_ndoc": SERVICE_NIT,
        "nvfac_fech": "2026-09-20 10:00:00",
        "nvfac_cufe": "",
        "nvtip_docu": "FAC",
        "nvfac_fpag": "",
        "nvfac_orde": nvfac_orde,
        "nvfac_rece": "",
        "nvfac_totp": 200000,
        "nvfac_esta": "E",
        "nvfac_ueve": "",
        "nvfac_conv": nvfac_conv,
        "nvmon_codi": "COP",
        "nvfac_stot": 200000,
        "nvfac_viva": 0,
        "nvpro_nomb": "PROVEEDOR SERVICIO",
    })
    store.insert("qp_SP_DetailLine", {
        "parent": DOC_NAME,
        "parenttype": "qp_SP_DocumentDetail",
        "nvpro_codi": "SRV-1",
        "nvdet_tcan": 2,
        "nvdet_valo": 100000,
        "nvdet_stot": 200000,
    })
    seeds.seed_homologation(store, SERVICE_NIT, "SRV-1", "ITEM-SRV-2")


class TestSimGpServiceSupplierInMemory(unittest.TestCase):

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

    def test_servicio_sin_oc_aprueba_automatico_ignorando_setup(self):
        _seed_doc(self.store, supplier_rule=None)
        with patch("qp_supplier_front.simulation.session.store",
                   return_value=self.store):
            for p in self._patched():
                p.start()
                self.addCleanup(p.stop)

            result = arapp.run_auto_approve(enqueue=False)

        self.assertFalse(result["skipped"])
        # El setup global (no_po) NO bloquea a un proveedor de servicio.
        self.assertIn(INVOICE_NUM, result["promoted"])
        row = self.store.get("qp_SP_DocumentDetail", DOC_NAME)
        self.assertEqual(row["nvfac_esta"], "A")
        inv = self.store.query("qp_SP_PurchaseInvoice",
                               filters={"name": DOC_NAME})
        self.assertEqual(len(inv), 1)
        self.assertEqual(inv[0]["qp_sync_flow"], "GP")

    def test_servicio_con_regla_proveedor_no_po_sin_oc_no_promueve(self):
        _seed_doc(self.store, supplier_rule="RULE-NO-PO")
        with patch("qp_supplier_front.simulation.session.store",
                   return_value=self.store):
            for p in self._patched():
                p.start()
                self.addCleanup(p.stop)

            result = arapp.run_auto_approve(enqueue=False)

        # La regla del PROVEEDOR exige OC: sin OC no se aprueba.
        self.assertNotIn(INVOICE_NUM, result.get("promoted") or [])
        row = self.store.get("qp_SP_DocumentDetail", DOC_NAME)
        self.assertEqual(row["nvfac_esta"], "E")
        self.assertEqual(
            self.store.query("qp_SP_PurchaseInvoice"), []
        )


if __name__ == "__main__":
    unittest.main()