# -*- coding: utf-8 -*-
"""
test_collection_sim_gp_in_memory.py
===================================
Aprobacion simulada de cuentas de cobro (collection) 100% en memoria con
backend GP: con el flag collection_invoices_simulation activo y backend="GP",
approve_collection_invoices_core usa el sender simulado GP y persiste en
memoria el qp_creation_backend="GP" (BCC + cuenta "Facturado", sin eventos).

Ejecutar con: python -m unittest qp_supplier_front.tests.test_collection_sim_gp_in_memory -v
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()

from qp_supplier_front.resources.collection_accounts import (  # noqa: E402
    _collection_invoice_base as base,
    runtime as collection_runtime,
)
from qp_supplier_front.simulation import (  # noqa: E402
    collection_invoices_memory as mem,
    collection_seeds as seeds,
    session,
)
from qp_supplier_front.simulation.store import MemoryStore  # noqa: E402


class TestCollectionSimGpInMemory(unittest.TestCase):

    def setUp(self):
        session.reset()
        self.store = MemoryStore()
        seeds.seed_collection_scenario(self.store)
        self.addCleanup(session.reset)

    def _run(self, doc_names):
        with patch.object(collection_runtime, "is_simulation_enabled",
                          return_value=True), \
             patch.object(base, "frappe", MagicMock()), \
             patch("qp_supplier_front.simulation.session.store",
                   return_value=self.store):
            return base.approve_collection_invoices_core(
                doc_names, backend="GP"
            )

    def test_aprobacion_gp_simulada_marca_bcc_y_backend_gp(self):
        result = self._run(["PI-SIM-0001"])

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(result["errors"], [])
        # doc_number simulado GP: SIM{noFacturaProveedor}
        self.assertEqual(result["approved"][0]["doc_number"], "SIMPI-SIM-0001")

        row = self.store.get("qp_SP_PurchaseInvoice", "PI-SIM-0001")
        self.assertEqual(row["qp_status"], "BCC")
        self.assertEqual(row["qp_creation_backend"], "GP")
        self.assertEqual(row["invoice_id"], "SIMPI-SIM-0001")

        ca = self.store.get("qp_SP_CollectionAccounts", "CA-SIM-0001")
        self.assertEqual(ca["status"], "Facturado")

        # Referencia GP/BC de confirmacion (igual que documenteme) sin eventos
        # ni enlace a documenteme.
        pi_bc = self.store.query("qp_SP_PurchaseInvoiceBC")
        self.assertEqual(len(pi_bc), 1)
        self.assertEqual(pi_bc[0]["invoice_id"], "SIMPI-SIM-0001")
        self.assertEqual(pi_bc[0]["purchase_invoice"], "PI-SIM-0001")
        self.assertEqual(len(self.store.query("qp_SP_EventLog")), 0)

    def test_aprobacion_bc_mantiene_backend_bc(self):
        with patch.object(collection_runtime, "is_simulation_enabled",
                          return_value=True), \
             patch.object(base, "frappe", MagicMock()), \
             patch("qp_supplier_front.simulation.session.store",
                   return_value=self.store):
            result = base.approve_collection_invoices_core(
                ["PI-SIM-0001"], backend="BC"
            )

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(result["errors"], [])
        # Persistencia sim registra el backend BC en qp_creation_backend.
        row = self.store.get("qp_SP_PurchaseInvoice", "PI-SIM-0001")
        self.assertEqual(row["qp_creation_backend"], "BC")
        # BC collection no crea la referencia de confirmacion.
        self.assertEqual(len(self.store.query("qp_SP_PurchaseInvoiceBC")), 0)


class TestCollectionSimGpDuplicateMemory(unittest.TestCase):

    def setUp(self):
        session.reset()
        self.store = MemoryStore()
        seeds.seed_collection_scenario(self.store)
        self.addCleanup(session.reset)

    def test_mark_duplicate_gp_nombra_gp(self):
        doc = mem.memory_get_docs(
            self.store, ["PI-SIM-0001"],
        )[0]
        mem.memory_mark_duplicate_registered(
            self.store, doc, "VNDDOCNM duplicado", "2026-09-11 10:00:00",
            backend="GP",
        )
        row = self.store.get("qp_SP_PurchaseInvoice", "PI-SIM-0001")
        self.assertEqual(row["qp_status"], "BCC")
        self.assertEqual(row["qp_creation_backend"], "GP")
        self.assertIn("en GP", row["qp_error_message"])
        notifications = self.store.query("qp_SP_PurchaseInvoiceNotification")
        self.assertTrue(any(
            "en GP" in n.get("notification_message") or ""
            for n in notifications
        ))

    def test_mark_duplicate_bc_nombra_bc(self):
        doc = mem.memory_get_docs(
            self.store, ["PI-SIM-0001"],
        )[0]
        mem.memory_mark_duplicate_registered(
            self.store, doc, "ya existe la factura", "2026-09-11 10:00:00",
            backend="BC",
        )
        row = self.store.get("qp_SP_PurchaseInvoice", "PI-SIM-0001")
        self.assertEqual(row["qp_creation_backend"], "BC")
        self.assertIn("en BC", row["qp_error_message"])


if __name__ == "__main__":
    unittest.main()