# -*- coding: utf-8 -*-
"""
test_sim_reject_in_memory.py
============================
Rechazo automatico en memoria: run_reject (simulation/reject_memory.py) sobre
el store de la sesion con eventos simulados (030/032/031). Contado -> R directo;
credito sin OC -> R; credito con OC -> no se rechaza.

Ejecutar con: python -m pytest qp_supplier_front/tests/test_sim_reject_in_memory.py -v
"""
import unittest
from unittest.mock import patch

from qp_supplier_front.simulation import reject_memory, seeds
from qp_supplier_front.simulation.store import MemoryStore

SIM_NIT = "999999999"


def _doc(store, name, nume, estado="E", conv="2", orde=None, ueve=""):
    store.insert("qp_SP_DocumentDetail", {
        "name": name, "nvfac_nume": nume, "nvpro_ndoc": SIM_NIT,
        "nvfac_cont": "12345", "nvfac_esta": estado, "nvfac_ueve": ueve,
        "nvfac_conv": conv, "nvfac_orde": orde or "",
    })


class TestRejectCredit(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()

    def test_credito_sin_oc_termina_en_r(self):
        _doc(self.store, "999999999:F1", "F1", conv="2", orde="PO-X")
        with patch(
            "qp_supplier_front.resources.documenteme.runtime.is_simulation_enabled",
            return_value=True):
            result = reject_memory.run_reject(self.store, doc_names=["999999999:F1"])
        self.assertEqual(result["rejected"], ["F1"])
        doc = self.store.get("qp_SP_DocumentDetail", "999999999:F1")
        self.assertEqual(doc["nvfac_esta"], "R")
        self.assertEqual(doc["nvfac_ueve"], "031")
        events = self.store.query("qp_SP_EventLog",
                                  filters={"parent": "999999999:F1"})
        self.assertEqual([e["event_code"] for e in events],
                         ["030", "032", "031"])

    def test_credito_con_oc_sembrada_no_se_rechaza(self):
        seeds.seed_purchase_order(self.store, "PO-X", headquarter="HQ01")
        _doc(self.store, "999999999:F1", "F1", conv="2", orde="PO-X")
        with patch(
            "qp_supplier_front.resources.documenteme.runtime.is_simulation_enabled",
            return_value=True):
            result = reject_memory.run_reject(self.store, doc_names=["999999999:F1"])
        self.assertEqual(result["rejected"], [])
        doc = self.store.get("qp_SP_DocumentDetail", "999999999:F1")
        self.assertEqual(doc["nvfac_esta"], "E")

    def test_contado_termina_en_r_sin_eventos(self):
        _doc(self.store, "999999999:F1", "F1", conv="1")
        with patch(
            "qp_supplier_front.resources.documenteme.runtime.is_simulation_enabled",
            return_value=True):
            result = reject_memory.run_reject(self.store, doc_names=["999999999:F1"])
        self.assertEqual(result["rejected"], ["F1"])
        doc = self.store.get("qp_SP_DocumentDetail", "999999999:F1")
        self.assertEqual(doc["nvfac_esta"], "R")
        self.assertEqual(
            len(self.store.query("qp_SP_EventLog",
                                 filters={"parent": "999999999:F1"})), 0)

    def test_doc_con_ueve_no_se_reprocesa(self):
        _doc(self.store, "999999999:F1", "F1", conv="2", ueve="031")
        with patch(
            "qp_supplier_front.resources.documenteme.runtime.is_simulation_enabled",
            return_value=True):
            result = reject_memory.run_reject(self.store, doc_names=["999999999:F1"])
        self.assertEqual(result["rejected"], [])

    def test_evento_fallido_queda_pendiente_con_alerta(self):
        _doc(self.store, "999999999:F1", "F1", conv="2", orde="PO-X")
        from qp_supplier_front.resources.documenteme import runtime, simulation
        bundle = {
            "event_http_fn": simulation.build_http_double(fail_all=True),
            "event_endpoint_fn": simulation.get_event_endpoint,
            "company_tax_id_fn": simulation.get_company_tax_id,
        }
        with patch.object(runtime, "resolve", return_value=bundle):
            result = reject_memory.run_reject(self.store, doc_names=["999999999:F1"])
        self.assertEqual(result["pending"], ["F1"])
        doc = self.store.get("qp_SP_DocumentDetail", "999999999:F1")
        self.assertEqual(doc["nvfac_esta"], "PR")
        alerts = self.store.query("qp_SP_Alert",
                                  filters={"parent": "999999999:F1"})
        self.assertEqual(len(alerts), 1)


if __name__ == "__main__":
    unittest.main()