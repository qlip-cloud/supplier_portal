# -*- coding: utf-8 -*-
"""
test_sim_scenario_in_memory.py
==============================
Escenario integral en memoria: sync (fases 1-2) + asignacion + auto-aprobacion
+ rechazo sobre los fixtures del escenario completo. Sin base de datos real.

El escenario de 11 facturas debe terminar en:
  - Rechazadas (R): SIM-FAC-0001, SIM-FAC-0002 (credito sin OC).
  - Aprobadas (A): contado (SIM-FAC-0003/0004) y credito cubierto por el banco
    de recibos (SIM-POA-0001/0002, SIM-POB-0001/0002).
  - Asignadas (E + assigned_users): SIM-POB-0003, SIM-POC-0001/0002
    (credito con OC cuya combinacion de recibos no la cubre).

Ejecutar con: python -m unittest qp_supplier_front.tests.test_sim_scenario_in_memory -v
"""
import unittest
from unittest.mock import MagicMock, patch

import qp_supplier_front.uses_cases.documents.sync_all_whitelist as saw  # noqa: E402
from qp_supplier_front.infrastructure.adapters.data_facade import DataFacade  # noqa: E402
from qp_supplier_front.resources.documenteme import auto_approve as arap  # noqa: E402
from qp_supplier_front.resources.documenteme import _approve_base as abase  # noqa: E402
from qp_supplier_front.services.enrich_document_list import enrich_document_list  # noqa: E402
from qp_supplier_front.simulation import session  # noqa: E402

SIM_NIT = "999999999"

REJECTED = {"SIM-FAC-0001", "SIM-FAC-0002"}
APPROVED = {
    "SIM-FAC-0003",
    "SIM-POA-0001", "SIM-POA-0002",
    "SIM-POB-0001", "SIM-POB-0002",
}
ASSIGNED = {"SIM-POB-0003", "SIM-POC-0001", "SIM-POC-0002", "SIM-FAC-0004"}


class TestSimScenarioInMemory(unittest.TestCase):

    def setUp(self):
        self.frappe_mock = MagicMock()
        self.frappe_mock.get_all.return_value = ["COMP-A"]
        session.reset()
        self.addCleanup(session.reset)

    def _patched(self):
        return [
            patch.object(saw, "frappe", self.frappe_mock),
            patch.object(saw.runtime, "is_simulation_enabled", return_value=True),
            patch.object(saw, "run_documenteme_stale_status_alerts"),
            patch.object(arap, "frappe", MagicMock()),
            patch.object(abase, "frappe", MagicMock()),
        ]

    def test_escenario_completo_estados_finales(self):
        for p in self._patched():
            p.start()
            self.addCleanup(p.stop)

        result = saw._sync_documents()
        created = result["created"]
        saw._launch_reject(created)

        store = session.store()
        states = {
            row["nvfac_nume"]: row["nvfac_esta"]
            for row in store.query("qp_SP_DocumentDetail")
        }
        self.assertEqual(len(states), 11)
        for nume in REJECTED:
            self.assertEqual(states[nume], "R", nume)
        for nume in APPROVED:
            self.assertEqual(states[nume], "A", nume)
        for nume in ASSIGNED:
            self.assertEqual(states[nume], "E", nume)

        # Aprobadas de credito notificaron 030/032/033; contado va directo a A.
        # Solo el contado CON OC aprueba (no_po); el contado SIN OC se asigna.
        row = store.query("qp_SP_DocumentDetail",
                          filters={"nvfac_nume": "SIM-FAC-0003"}, limit=1)[0]
        self.assertEqual(row["nvfac_ueve"], "")
        self.assertEqual(row["qp_is_event_completed"], 1)
        for nume in ("SIM-POA-0001", "SIM-POB-0002"):
            row = store.query("qp_SP_DocumentDetail",
                              filters={"nvfac_nume": nume}, limit=1)[0]
            self.assertEqual(row["nvfac_ueve"], "033")
            self.assertEqual(row["qp_is_event_completed"], 1)

    def test_asignadas_tienen_usuario_y_consumo_de_recibos(self):
        for p in self._patched():
            p.start()
            self.addCleanup(p.stop)

        result = saw._sync_documents()
        saw._launch_reject(result["created"])

        store = session.store()
        for nume in ASSIGNED:
            line = "{}:{}".format(SIM_NIT, nume)
            assigned = store.query(
                "qp_SP_SyncLineAssignedUser", filters={"parent": line})
            self.assertEqual(len(assigned), 1, nume)
            self.assertEqual(assigned[0]["user"], "asignado@sim.local")

        # Recibos consumidos solo en los aprobados (PO-A completo, PO-B parcial).
        consumed = {
            row["name"] for row in store.query("qp_SP_PurchaseReceipt",
                                               filters={"qp_invoice": ["is", "set"]})
        }
        self.assertTrue({"REC-A-1", "REC-A-4"}.issubset(consumed))
        self.assertIn("REC-B-1", consumed)
        self.assertIn("REC-B-2", consumed)
        # No cubiertos: REC-B-3 y todo el banco C siguen sin consumir.
        self.assertNotIn("REC-B-3", consumed)
        self.assertFalse({"REC-C-1", "REC-C-2"}.intersection(consumed))

        # Todas las aprobadas persistieron su factura en BC.
        invoices = store.query("qp_SP_PurchaseInvoice")
        self.assertEqual(len(invoices), len(APPROVED))
        self.assertTrue(all(row.get("invoice_id") for row in invoices))

    def test_vista_oc_y_recibos_via_facade(self):
        for p in self._patched():
            p.start()
            self.addCleanup(p.stop)

        result = saw._sync_documents()
        saw._launch_reject(result["created"])

        store = session.store()
        facade = DataFacade(store=store)
        docs = store.query("qp_SP_DocumentDetail")

        doc_poa = next(d for d in docs if d["nvfac_nume"] == "SIM-POA-0001")
        enrich_document_list([doc_poa], "qp_SP_DocumentDetail", data=facade)
        self.assertEqual(doc_poa["ordenes_compra"], ["PO-A-0001"])
        # Solo los recibos asignados a ESTA factura (qp_invoice == nvfac_nume):
        # SIM-POA-0001 consume REC-A-1 y REC-A-2 (500+1500); el resto del banco
        # A no forma parte de la factura y no se muestra.
        self.assertEqual(
            doc_poa["recepciones"],
            ["RECIBO A1 · 500", "RECIBO A2 · 1500"],
        )
        self.assertEqual(
            [p["codigo"] for p in doc_poa["productos_orden_compra"]],
            ["ITEM-POA1", "ITEM-POA2"],
        )
        self.assertEqual(len(doc_poa["productos_recepcion"]), 2)

        # La hermana de la misma OC muestra solo SU recibos asignados.
        doc_poa2 = next(d for d in docs if d["nvfac_nume"] == "SIM-POA-0002")
        enrich_document_list([doc_poa2], "qp_SP_DocumentDetail", data=facade)
        self.assertEqual(
            doc_poa2["recepciones"],
            ["RECIBO A3 · 1000", "RECIBO A4 · 3000"],
        )

        # Factura asignada (sin aprobar) no tiene recibos asignados.
        doc_pob3 = next(d for d in docs if d["nvfac_nume"] == "SIM-POB-0003")
        enrich_document_list([doc_pob3], "qp_SP_DocumentDetail", data=facade)
        self.assertEqual(doc_pob3["recepciones"], [])
        self.assertEqual(doc_pob3["productos_recepcion"], [])

        # Contado sin OC no tiene OC ni recibos visibles.
        doc_cash = next(d for d in docs if d["nvfac_nume"] == "SIM-FAC-0004")
        enrich_document_list([doc_cash], "qp_SP_DocumentDetail", data=facade)
        self.assertEqual(doc_cash["ordenes_compra"], [])
        self.assertEqual(doc_cash["recepciones"], [])


if __name__ == "__main__":
    unittest.main()