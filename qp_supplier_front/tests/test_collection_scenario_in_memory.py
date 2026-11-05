# -*- coding: utf-8 -*-
"""
tests/test_collection_scenario_in_memory.py
============================================
Escenario SIMULADOR del flujo de cuentas de cobro -> facturas de compra 100%
en memoria. Reproduce el ciclo completo de una cuenta de cobro sobre el
MemoryStore de la sesion, sin Base de Datos ni Frappe:

1. Crear cuenta de cobro -> la factura se crea y EVALUA con la regla de CREDITO
   (banco de recepciones): cubierta -> V; no cubierta -> E + ASIGNACION
   automatica (child assigned_users).
2. Aprobar la factura cubierta -> BCC + cuenta "Facturado" (sin eventos).
3. Confirmar -> A.
4. Documentos adjuntos (docs_attach) y comentarios/lectura en memoria.

Es el "simulador" del proceso collection: mismo escenario que
docs/SIMULACION-COLLECTION.md.
"""
import unittest

from qp_supplier_front.resources.documenteme import simulation as doc_simulation
from qp_supplier_front.simulation import (
    collection_invoices_memory as mem,
    collection_seeds as seeds,
    documents_memory as dm,
    references_memory as ref,
)
from qp_supplier_front.simulation import session
from qp_supplier_front.simulation.seeds import seed_purchase_receipt
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


class TestCollectionScenarioInMemory(unittest.TestCase):

    def setUp(self):
        session.reset()
        self.store = MemoryStore()
        seeds.seed_collection_scenario(self.store)
        self.addCleanup(session.reset)

    def test_ciclo_completo_cuenta_cubierta(self):
        # Nueva cuenta sobre PO-CA-0001 (disponible 400k) por 200k, cubierta
        # por el banco (recibo 200k) y con archivo adjunto.
        result = mem.memory_create_collection_account(
            self.store, "PO-CA-0001", 200000,
            docs="/files/factura-collection.pdf",
        )
        self.assertIsNone(result.get("error"))
        pi = result["purchase_invoice"]

        # Evaluacion credito: cubierta -> V.
        self.assertEqual(
            self.store.get_value("qp_SP_PurchaseInvoice", pi, "qp_status"), "V"
        )

        # Documento adjunto registrado en la factura.
        docs = self.store.query(
            "qp_SP_PurchaseInvoiceDoc", filters={"parent": pi})
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["file_name"], "factura-collection.pdf")

        # Aprobacion -> BCC + cuenta Facturado, sin eventos, sin BCC doc.
        result_ap = _run_approve(self.store, [pi])
        self.assertEqual(len(result_ap["approved"]), 1)
        self.assertEqual(result_ap["errors"], [])
        row = self.store.get("qp_SP_PurchaseInvoice", pi)
        self.assertEqual(row["qp_status"], "BCC")
        account = self.store.get_value(
            "qp_SP_CollectionAccounts", result["name"], "status")
        self.assertEqual(account, "Facturado")
        self.assertEqual(len(self.store.query("qp_SP_PurchaseInvoiceBC")), 0)

        # Confirmacion externa -> A.
        invoice_id = result_ap["approved"][0]["doc_number"]
        ok = mem.memory_set_confirmation(self.store, invoice_id, "CONF-X")["ok"]
        self.assertTrue(ok)
        self.assertEqual(
            self.store.get_value("qp_SP_PurchaseInvoice", pi, "qp_status"), "A"
        )

    def test_ciclo_cuenta_no_cubierta_se_asigna_y_rechaza(self):
        # Nueva cuenta sobre PO-CA-0001 por 300k: el banco (200k/400k/400k) no
        # tiene combinacion exacta -> E asignada, sin error urgente.
        result = mem.memory_create_collection_account(
            self.store, "PO-CA-0001", 300000
        )
        self.assertIsNone(result.get("error"))
        pi = result["purchase_invoice"]

        self.assertEqual(
            self.store.get_value("qp_SP_PurchaseInvoice", pi, "qp_status"), "E"
        )
        assigned = self.store.query(
            "qp_SP_PurchaseInvoiceAssignedUser",
            filters={"parent": pi, "parenttype": "qp_SP_PurchaseInvoice"},
        )
        self.assertEqual([r["user"] for r in assigned], [seeds.ASSIGNEE_EMAIL])

        notifs = self.store.query(
            "qp_SP_PurchaseInvoiceNotification",
            filters={"parent": pi},
        )
        self.assertEqual(notifs, [])

        # Rechazo sincrono -> R + notificacion Alerta.
        mem.memory_reject(self.store, [pi], "No aplica")
        self.assertEqual(
            self.store.get_value("qp_SP_PurchaseInvoice", pi, "qp_status"), "R"
        )
        alerts = self.store.query(
            "qp_SP_PurchaseInvoiceNotification",
            filters={"parent": pi, "status": "Abierta"},
        )
        self.assertTrue(alerts)
        self.assertEqual(alerts[0]["notification_type"], "Alerta")

    def test_comentarios_en_flujo(self):
        # Un comentario en memoria via data (facade) sobre PI-SIM-0002
        # (asignada) y su marca de lectura.
        from qp_supplier_front.infrastructure.adapters.data_facade import DataFacade
        facade = DataFacade(store=self.store)

        facade.insert_child("qp_SP_PurchaseInvoiceComment", "PI-SIM-0002", {
            "message": "Por favor verificar recepcion",
            "entry_by": "Asignado Collection",
            "entry_date": "2026-09-08 11:00:00",
        })
        comments = facade.get_all(
            "qp_SP_PurchaseInvoiceComment",
            filters={"parent": "PI-SIM-0002"},
            fields=["message", "entry_by", "entry_date"],
        )
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["message"], "Por favor verificar recepcion")

        facade.insert_child("qp_SP_PurchaseInvoiceCommentRead", "PI-SIM-0002", {
            "user": "Administrator",
            "last_read": "2026-09-08 12:00:00",
        })
        reads = facade.get_all(
            "qp_SP_PurchaseInvoiceCommentRead",
            filters={"parent": "PI-SIM-0002"},
            fields=["user", "last_read"],
        )
        self.assertEqual(len(reads), 1)
        self.assertEqual(reads[0]["user"], "Administrator")


if __name__ == "__main__":
    unittest.main()