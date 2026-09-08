# -*- coding: utf-8 -*-
"""
tests/test_collection_sim_in_memory.py
======================================
Escenario del modo simulador de cuentas de cobro 100% en memoria: crear
cuenta -> factura V/E; aprobar -> BCC + cuenta "Facturado" sin crear
qp_SP_PurchaseInvoiceBC ni eventos; rechazar -> R; confirmar -> A.

No toca la base de datos real ni Frappe.
"""
import unittest
from unittest.mock import MagicMock, patch

from qp_supplier_front.resources.documenteme import simulation as doc_simulation
from qp_supplier_front.simulation import (
    collection_invoices_memory as mem,
    collection_seeds as seeds,
    documents_memory as dm,
    references_memory as ref,
)
from qp_supplier_front.simulation import session
from qp_supplier_front.simulation.store import MemoryStore
from qp_supplier_front.uses_cases.collection_invoices.approve import (
    approve_collection_invoices,
)


def _run_approve(store, doc_names, now="2026-09-03 15:30:00"):
    return approve_collection_invoices(
        doc_names,
        get_docs_fn=lambda names: mem.memory_get_docs(store, names),
        get_lines_fn=lambda doc: mem.memory_get_lines(store, doc),
        get_headquarter_fn=lambda po: ref.memory_get_headquarter(store, po),
        po_exists_fn=lambda po: ref.memory_po_exists(store, po),
        receipt_bank_fn=lambda po: ref.memory_get_receipt_bank(store, po),
        resolve_rule_fn=lambda doc: ref.memory_resolve_rule(store, doc),
        consume_receipts_fn=lambda doc, names: dm.memory_consume_receipts(
            store, doc, names),
        send_request_fn=doc_simulation.send_purchase_invoice_request,
        parse_doc_numbers_fn=lambda r: (r or {}).get("invoices") or [],
        persist_invoice_fn=lambda doc, doc_number, when: mem.memory_persist_invoice(
            store, doc, doc_number, when),
        mark_registered_fn=lambda doc, doc_number=None: mem.memory_mark_registered(
            store, doc, doc_number),
        mark_error_fn=lambda doc, error: mem.memory_mark_error(store, doc, error),
        mark_duplicate_registered_fn=lambda doc, error, when: mem.memory_mark_duplicate_registered(
            store, doc, error, when),
        commit_fn=lambda: None,
        now=now,
    )


class TestCollectionSimInMemory(unittest.TestCase):

    def setUp(self):
        session.reset()
        self.store = MemoryStore()
        seeds.seed_collection_scenario(self.store)
        self.addCleanup(session.reset)

    def test_seeds_del_escenario(self):
        self.assertEqual(
            self.store.get_value("qp_SP_PurchaseInvoice", "PI-SIM-0001", "qp_status"),
            "V",
        )
        self.assertEqual(
            self.store.get_value("qp_SP_PurchaseInvoice", "PI-SIM-0002", "qp_status"),
            "V",
        )
        # Contado que viola la regla no_receipt (PO sin recibos) -> E.
        self.assertEqual(
            self.store.get_value("qp_SP_PurchaseInvoice", "PI-SIM-0003", "qp_status"),
            "E",
        )
        notifs = self.store.query(
            "qp_SP_PurchaseInvoiceNotification",
            filters={"parent": "PI-SIM-0003"},
        )
        self.assertTrue(notifs)
        self.assertEqual(notifs[0]["notification_type"], "ErrorUrgente")

    def test_crear_cuenta_evalua_factura(self):
        result = mem.memory_create_collection_account(
            self.store, "PO-CA-0001", 200000
        )
        self.assertIsNone(result.get("error"))
        pi = result["purchase_invoice"]
        self.assertEqual(
            self.store.get_value("qp_SP_PurchaseInvoice", pi, "qp_status"), "V"
        )

    def test_articular_cuenta_con_monto_superior_al_disponible(self):
        # Disponible = 1.000.000 (PO) - 600.000 (PI-SIM-0001) = 400.000.
        result = mem.memory_create_collection_account(
            self.store, "PO-CA-0001", 500000
        )
        self.assertIn("error", result)

    def test_aprobar_marca_bcc_y_cuenta_facturado_sin_eventos(self):
        result = _run_approve(self.store, ["PI-SIM-0001"])

        self.assertEqual(len(result["approved"]), 1)
        self.assertEqual(result["approved"][0]["doc_number"], "SIMPI-SIM-0001")
        self.assertEqual(result["errors"], [])

        row = self.store.get("qp_SP_PurchaseInvoice", "PI-SIM-0001")
        self.assertEqual(row["qp_status"], "BCC")
        self.assertTrue(row["invoice_id"])

        ca = self.store.get("qp_SP_CollectionAccounts", "CA-SIM-0001")
        self.assertEqual(ca["status"], "Facturado")

        # Sin confirmacion encolada ni eventos a documenteme.
        self.assertEqual(
            len(self.store.query("qp_SP_PurchaseInvoiceBC")), 0
        )
        self.assertEqual(len(self.store.query("qp_SP_EventLog")), 0)

    def test_rechazo_es_sincrono_y_local(self):
        mem.memory_reject(self.store, ["PI-SIM-0002"], "No aplica", True)
        row = self.store.get("qp_SP_PurchaseInvoice", "PI-SIM-0002")
        self.assertEqual(row["qp_status"], "R")
        self.assertEqual(row["qp_motive"], "No aplica")
        self.assertEqual(row["qp_reject_is_invoice_error"], 1)

    def test_aprobar_resuelve_notificaciones_abiertas(self):
        mem.memory_insert_notification(
            self.store, "PI-SIM-0001", "Error previo",
            notification_type="ErrorUrgente",
        )
        result = _run_approve(self.store, ["PI-SIM-0001"])

        self.assertEqual(len(result["approved"]), 1)
        open_notifs = [
            n for n in self.store.query(
                "qp_SP_PurchaseInvoiceNotification",
                filters={"parent": "PI-SIM-0001"},
            )
            if n["status"] == "Abierta"
        ]
        self.assertEqual(len(open_notifs), 0)

    def test_factura_contado_viola_regla_no_receipt(self):
        # Contado + regla no_receipt activa: sin recibos -> E con notificacion.
        pi_status = self.store.get_value(
            "qp_SP_PurchaseInvoice", "PI-SIM-0003", "qp_status"
        )
        self.assertEqual(pi_status, "E")
        notifs = self.store.query(
            "qp_SP_PurchaseInvoiceNotification",
            filters={"parent": "PI-SIM-0003"},
        )
        self.assertTrue(notifs)
        self.assertEqual(notifs[0]["notification_type"], "ErrorUrgente")
        self.assertEqual(notifs[0]["status"], "Abierta")

    def test_aprobar_respeta_regla_no_receipt(self):
        # Aunque sea contado, la regla no_receipt bloquea la aprobacion.
        result = _run_approve(self.store, ["PI-SIM-0003"])
        self.assertEqual(result["approved"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(
            self.store.get_value("qp_SP_PurchaseInvoice", "PI-SIM-0003", "qp_status"),
            "E",
        )

    def test_rechazo_inserta_notificacion(self):
        mem.memory_reject(self.store, ["PI-SIM-0002"], "No aplica", True)
        open_reject = [
            n for n in self.store.query(
                "qp_SP_PurchaseInvoiceNotification",
                filters={"parent": "PI-SIM-0002"},
            )
            if n["status"] == "Abierta"
            and str(n["notification_message"]).startswith("Factura rechazada")
        ]
        self.assertTrue(open_reject)

    def test_confirmacion_marca_a(self):
        result = _run_approve(self.store, ["PI-SIM-0001"])
        invoice_id = result["approved"][0]["doc_number"]

        confirmation = mem.memory_set_confirmation(
            self.store, invoice_id, "CONF-1"
        )
        self.assertTrue(confirmation["ok"])
        row = self.store.get("qp_SP_PurchaseInvoice", "PI-SIM-0001")
        self.assertEqual(row["qp_status"], "A")
        self.assertEqual(row["confirmation_id"], "CONF-1")

    def test_store_soporta_filtro_between(self):
        from qp_supplier_front.simulation.store import _match_value

        self.assertTrue(_match_value("2026-09-01", "between", ["2026-08-01", "2026-09-30"]))
        self.assertFalse(_match_value("2026-10-01", "between", ["2026-08-01", "2026-09-30"]))


if __name__ == "__main__":
    unittest.main()