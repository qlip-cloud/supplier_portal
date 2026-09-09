# -*- coding: utf-8 -*-
"""
tests/test_collection_sim_in_memory.py
======================================
Escenario del modo simulador de cuentas de cobro 100% en memoria: crear
    cuenta -> factura V (banco cubre) o E asignada (banco no cubre); aprobar
    -> BCC + cuenta "Facturado" sin crear qp_SP_PurchaseInvoiceBC ni eventos;
    rechazar -> R; confirmar -> A.

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


class TestCollectionSimInMemory(unittest.TestCase):

    def setUp(self):
        session.reset()
        self.store = MemoryStore()
        seeds.seed_collection_scenario(self.store)
        self.addCleanup(session.reset)

    def _assigned_users(self, pi_name):
        return self.store.query(
            "qp_SP_PurchaseInvoiceAssignedUser",
            filters={"parent": pi_name, "parenttype": "qp_SP_PurchaseInvoice"},
            fields=["user"],
        )

    def test_seeds_del_escenario(self):
        # Cubierta por el banco (200k+400k = 600k) -> V.
        self.assertEqual(
            self.store.get_value("qp_SP_PurchaseInvoice", "PI-SIM-0001", "qp_status"),
            "V",
        )
        # Banco 100k no cubre 500k -> E asignada.
        self.assertEqual(
            self.store.get_value("qp_SP_PurchaseInvoice", "PI-SIM-0002", "qp_status"),
            "E",
        )
        self.assertTrue(self._assigned_users("PI-SIM-0002"))
        # Sin banco -> E asignada (sin notificacion ErrorUrgente).
        self.assertEqual(
            self.store.get_value("qp_SP_PurchaseInvoice", "PI-SIM-0003", "qp_status"),
            "E",
        )
        self.assertTrue(self._assigned_users("PI-SIM-0003"))
        notifs = self.store.query(
            "qp_SP_PurchaseInvoiceNotification",
            filters={"parent": "PI-SIM-0003"},
        )
        self.assertEqual(notifs, [])

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

    def test_credit_no_cubierta_queda_e_sin_error_urgente(self):
        # Credito sin banco que cubra: E asignada, sin notificacion urgente.
        pi_status = self.store.get_value(
            "qp_SP_PurchaseInvoice", "PI-SIM-0003", "qp_status"
        )
        self.assertEqual(pi_status, "E")
        notifs = self.store.query(
            "qp_SP_PurchaseInvoiceNotification",
            filters={"parent": "PI-SIM-0003"},
        )
        self.assertEqual(notifs, [])
        self.assertTrue(self._assigned_users("PI-SIM-0003"))

    def test_aprobar_respeta_banco_insuficiente(self):
        # Credito sin recepciones que cubran: no se aprueba automaticamente.
        result = _run_approve(self.store, ["PI-SIM-0003"])
        self.assertEqual(result["approved"], [])
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(
            self.store.get_value("qp_SP_PurchaseInvoice", "PI-SIM-0003", "qp_status"),
            "E",
        )

    def test_crear_cuenta_no_cubierta_se_asigna(self):
        # Nueva OC con banco insuficiente (100k vs 500k) -> E asignada.
        seeds.seed_collection_po(
            self.store, "PO-CA-0004", "999999999", 1000000)
        seeds.seed_collection_po_item(
            self.store, "PO-CA-0004", "ITEM-0009", 1, 1000000)
        seed_purchase_receipt(
            self.store, "REC-CA4-1", "PO-CA-0004", 100000,
            posting_date="2026-08-28")

        result = mem.memory_create_collection_account(
            self.store, "PO-CA-0004", 500000
        )
        self.assertIsNone(result.get("error"))
        pi = result["purchase_invoice"]
        self.assertEqual(
            self.store.get_value("qp_SP_PurchaseInvoice", pi, "qp_status"),
            "E",
        )
        self.assertTrue(self._assigned_users(pi))

    def test_asignacion_automatica_del_escenario(self):
        assigned_2 = self._assigned_users("PI-SIM-0002")
        assigned_3 = self._assigned_users("PI-SIM-0003")
        self.assertEqual(
            [u["user"] for u in assigned_2], [seeds.ASSIGNEE_EMAIL]
        )
        self.assertEqual(
            [u["user"] for u in assigned_3], [seeds.ASSIGNEE_EMAIL]
        )

    def test_crear_cuenta_con_docs_crea_docs_attach(self):
        # El archivo adjunto (docs) de la cuenta se guarda en la tabla de
        # documentos de la FACTURA (child docs_attach), igual que documenteme.
        seeds.seed_collection_po(
            self.store, "PO-CA-0005", "999999999", 1000000)
        seeds.seed_collection_po_item(
            self.store, "PO-CA-0005", "ITEM-0010", 1, 1000000)

        result = mem.memory_create_collection_account(
            self.store, "PO-CA-0005", 500000,
            docs="/files/parafiscales.pdf",
        )
        self.assertIsNone(result.get("error"))
        pi = result["purchase_invoice"]

        docs = self.store.query(
            "qp_SP_PurchaseInvoiceDoc",
            filters={"parent": pi, "parenttype": "qp_SP_PurchaseInvoice"},
        )
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["file_url"], "/files/parafiscales.pdf")
        self.assertEqual(docs[0]["file_name"], "parafiscales.pdf")
        self.assertEqual(docs[0]["file_id"], "")

        # La cuenta conserva el archivo en su campo docs (Attach).
        self.assertEqual(
            self.store.get_value(
                "qp_SP_CollectionAccounts", result["name"], "docs"),
            "/files/parafiscales.pdf",
        )

    def test_crear_cuenta_sin_docs_no_crea_docs_attach(self):
        seeds.seed_collection_po(
            self.store, "PO-CA-0006", "999999999", 1000000)
        seeds.seed_collection_po_item(
            self.store, "PO-CA-0006", "ITEM-0011", 1, 1000000)

        result = mem.memory_create_collection_account(
            self.store, "PO-CA-0006", 500000
        )
        self.assertIsNone(result.get("error"))
        docs = self.store.query(
            "qp_SP_PurchaseInvoiceDoc",
            filters={"parent": result["purchase_invoice"]},
        )
        self.assertEqual(docs, [])

    def test_comentarios_y_lectura_en_memoria(self):
        # Los endpoints de comentarios escriben con data.insert_child (ruta
        # memoria) y leen con data.get_all; se verifica la persistencia.
        from qp_supplier_front.infrastructure.adapters.data_facade import DataFacade
        facade = DataFacade(store=self.store)

        facade.insert_child("qp_SP_PurchaseInvoiceComment", "PI-SIM-0002", {
            "message": "Hola proveedor",
            "entry_by": "Administrator",
            "entry_date": "2026-09-08 10:00:00",
        })

        comments = facade.get_all(
            "qp_SP_PurchaseInvoiceComment",
            filters={"parent": "PI-SIM-0002"},
            fields=["message", "entry_by", "entry_date"],
        )
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["message"], "Hola proveedor")

        facade.insert_child("qp_SP_PurchaseInvoiceCommentRead", "PI-SIM-0002", {
            "user": "Administrator",
            "last_read": "2026-09-08 10:30:00",
        })
        reads = facade.get_all(
            "qp_SP_PurchaseInvoiceCommentRead",
            filters={"parent": "PI-SIM-0002"},
            fields=["user", "last_read"],
        )
        self.assertEqual(len(reads), 1)
        self.assertEqual(reads[0]["user"], "Administrator")

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