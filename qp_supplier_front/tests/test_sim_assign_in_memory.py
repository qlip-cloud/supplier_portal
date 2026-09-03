# -*- coding: utf-8 -*-
"""
test_sim_assign_in_memory.py
=============================
Asignacion automatica simulada en memoria: las facturas de credito con OC
sin combinacion exacta de recepciones (banco) quedan asignadas a los usuarios
de qp_SP_AssignmentConfig; las cubiertas y los contados (sin regla) no.

Ejecutar con: python -m unittest qp_supplier_front.tests.test_sim_assign_in_memory -v
"""
import unittest

from qp_supplier_front.simulation import assign_memory
from qp_supplier_front.simulation import seeds
from qp_supplier_front.simulation.store import MemoryStore

SIM_NIT = "999999999"


def _seed_doc(store, nume, estado, orde, stot, conv):
    name = "{}:{}".format(SIM_NIT, nume)
    store.insert("qp_SP_DocumentDetail", {
        "name": name,
        "nvfac_nume": nume,
        "nvpro_ndoc": SIM_NIT,
        "nvfac_esta": estado,
        "nvfac_ueve": "",
        "nvfac_orde": orde,
        "nvfac_stot": stot,
        "nvfac_totp": stot,
        "nvfac_conv": conv,
        "document_sync_line": name,
    })
    store.insert("qp_SP_DocumentSyncLine", {
        "name": name,
        "nvfac_nume": nume,
        "assigned_to": None,
        "is_completed": 1,
    })


class TestSimAssignInMemory(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()
        seeds.seed_scenario(self.store)
        # Cubierta (no se asigna) y descubiertas (se asignan).
        _seed_doc(self.store, "SIM-POB-0001", "E", "PO-POB-0001", 1000, "2")
        _seed_doc(self.store, "SIM-POB-0003", "E", "PO-POB-0003", 2500, "2")
        _seed_doc(self.store, "SIM-POC-0001", "E", "PO-POC-0001", 1000, "2")
        # Contado con OC (no rompe no_po -> no se asigna) y contado sin OC
        # (rompe no_po -> se asigna via catch-all).
        _seed_doc(self.store, "SIM-FAC-0003", "E", "PO-SIM-0001", 400000, "1")
        _seed_doc(self.store, "SIM-FAC-0004", "E", "", 600000, "1")

    def test_asigna_solo_descubiertas(self):
        assigned = assign_memory.run_auto_assign(self.store)
        self.assertEqual(
            sorted(assigned),
            ["999999999:SIM-FAC-0004",
             "999999999:SIM-POB-0003",
             "999999999:SIM-POC-0001"],
        )

    def test_add_assignees_es_idempotente_y_agrega_child(self):
        line = "999999999:SIM-POB-0003"
        assign_memory.run_auto_assign(self.store)
        assign_memory.run_auto_assign(self.store)
        rows = self.store.query(
            "qp_SP_SyncLineAssignedUser", filters={"parent": line})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["user"], seeds.ASSIGNEE_EMAIL)

    def test_contado_cubierto_y_oc_cubierta_no_reciben_asignacion(self):
        assign_memory.run_auto_assign(self.store)
        for nume in ("SIM-POB-0003", "SIM-POC-0001", "SIM-FAC-0004"):
            self.assertGreater(self.store.count(
                "qp_SP_SyncLineAssignedUser",
                filters={"parent": "{}:{}".format(SIM_NIT, nume)}), 0)
        for nume in ("SIM-POB-0001", "SIM-FAC-0003"):
            self.assertEqual(self.store.count(
                "qp_SP_SyncLineAssignedUser",
                filters={"parent": "{}:{}".format(SIM_NIT, nume)}), 0)


if __name__ == "__main__":
    unittest.main()