# -*- coding: utf-8 -*-
"""
test_confirmation_endpoints.py
==============================
Pruebas unitarias para resources/documenteme/confirmation.py.

Frappe se inyecta en sys.modules como mock. Cada test crea su propio mock de
frappe para evitar contaminacion entre pruebas. Verifica la localizacion por
invoice_id, el guardado de confirmation_id y la transicion a estado "PA".
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

_identity = lambda fn: fn  # noqa: E731

frappe_mock = MagicMock()
frappe_mock.response = {}
frappe_mock.whitelist.side_effect = lambda *a, **k: _identity
sys.modules["frappe"] = frappe_mock
sys.modules["frappe.utils"] = MagicMock()

from qp_supplier_front.resources.documenteme import confirmation as mod  # noqa: E402


class TestFindDocumentByDocNumber(unittest.TestCase):

    def test_encuentra_por_doc_number(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = ["FAC001"]
        frappe_mock.db.exists.return_value = 1

        with patch.object(mod, "frappe", frappe_mock):
            doc = mod.find_document_by_invoice_id("123")

        self.assertEqual(doc["name"], "FAC001")
        self.assertEqual(doc["invoice_id"], "123")
        frappe_mock.get_all.assert_called_once_with(
            "qp_SP_PurchaseInvoice",
            filters={"invoice_id": "123"},
            pluck="name",
            limit=1,
        )

    def test_none_si_no_existe_invoice(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = []
        with patch.object(mod, "frappe", frappe_mock):
            doc = mod.find_document_by_invoice_id("999")
        self.assertIsNone(doc)

    def test_none_si_docnumber_vacio(self):
        frappe_mock = MagicMock()
        with patch.object(mod, "frappe", frappe_mock):
            doc = mod.find_document_by_invoice_id("")
        self.assertIsNone(doc)
        frappe_mock.get_all.assert_not_called()

    def test_none_si_no_existe_documentdetail(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = ["FAC001"]
        frappe_mock.db.exists.return_value = None
        with patch.object(mod, "frappe", frappe_mock):
            doc = mod.find_document_by_invoice_id("123")
        self.assertIsNone(doc)


class TestSetConfirmationId(unittest.TestCase):

    def test_guarda_confirmation_id(self):
        frappe_mock = MagicMock()
        doc = {"name": "FAC001", "invoice_id": "123"}
        with patch.object(mod, "frappe", frappe_mock):
            mod.set_confirmation_id(doc, "CONF-XYZ")
        frappe_mock.db.set_value.assert_called_once_with(
            "qp_SP_PurchaseInvoice",
            {"invoice_id": "123"},
            "confirmation_id",
            "CONF-XYZ",
        )


class TestMarkPendingApproval(unittest.TestCase):

    def test_marca_pa(self):
        frappe_mock = MagicMock()
        doc = {"name": "FAC001"}
        with patch.object(mod, "frappe", frappe_mock):
            mod.mark_pending_approval(doc)
        frappe_mock.db.set_value.assert_called_once_with(
            "qp_SP_DocumentDetail", "FAC001", "nvfac_esta", "PA"
        )


class TestEnqueueApprove(unittest.TestCase):

    def test_llama_a_auto_approve_confirmation(self):
        doc = {"name": "FAC001", "invoice_id": "123"}
        with patch.object(mod, "approval") as approval_mock:
            mod.enqueue_approve(doc)
        approval_mock.enqueue_approve_confirmation.assert_called_once_with(
            "FAC001"
        )


class TestActualizarDocumento(unittest.TestCase):

    def test_respuesta_ok(self):
        # Frappe genuino compartido para el response handler
        from qp_supplier_front.resources import response as resp_mod
        frappe_global = MagicMock()
        frappe_global.response = {}
        with patch.object(resp_mod, "frappe", frappe_global), \
             patch.object(mod, "process_confirmation") as process:
            process.return_value = {
                "ok": True,
                "errors": [],
                "doc": {"name": "FAC001", "invoice_id": "123"},
            }
            mod.update_document("123", "CONF-XYZ")
        self.assertEqual(frappe_global.response["http_status_code"], 200)

    def test_error_cuando_no_ok(self):
        from qp_supplier_front.resources import response as resp_mod
        frappe_global = MagicMock()
        frappe_global.response = {}
        with patch.object(resp_mod, "frappe", frappe_global), \
             patch.object(mod, "process_confirmation") as process:
            process.return_value = {
                "ok": False,
                "errors": ["No se encontro una factura con invoice_id 999"],
                "doc": None,
            }
            mod.update_document("999", "CONF-XYZ")
        self.assertEqual(frappe_global.response["http_status_code"], 400)


class TestOnPurchaseInvoiceBcUpdate(unittest.TestCase):

    def _doc(self, confirmation_id="00001", before_confirmation_id=None,
             purchase_invoice="FAC001"):
        doc = MagicMock()
        doc.name = "BCID001"
        doc.get.side_effect = lambda key, default=None: (
            confirmation_id if key == "confirmation_id"
            else purchase_invoice if key == "purchase_invoice"
            else default
        )
        before = None
        if before_confirmation_id is not None:
            before = MagicMock()
            before.get.return_value = (
                before_confirmation_id if before_confirmation_id else None
            )
        doc.get_doc_before_save.return_value = before
        return doc

    def test_marca_pa_y_encola_cuando_confirmation_id_nuevo(self):
        frappe_mock = MagicMock()
        frappe_mock.db.exists.return_value = 1
        doc = self._doc(confirmation_id="00001", before_confirmation_id=None)

        with patch.object(mod, "frappe", frappe_mock), \
             patch.object(mod, "approval") as approval_mock:
            mod.on_purchase_invoice_bc_update(doc, "on_update")

        frappe_mock.db.set_value.assert_called_once_with(
            "qp_SP_DocumentDetail", "FAC001", "nvfac_esta", "PA"
        )
        approval_mock.enqueue_approve_confirmation.assert_called_once_with(
            "FAC001"
        )
        frappe_mock.db.commit.assert_called_once()

    def test_no_dispara_si_confirmation_id_vacio(self):
        frappe_mock = MagicMock()
        doc = self._doc(confirmation_id=None, before_confirmation_id=None)

        with patch.object(mod, "frappe", frappe_mock), \
             patch.object(mod, "approval") as approval_mock:
            mod.on_purchase_invoice_bc_update(doc, "on_update")

        frappe_mock.db.set_value.assert_not_called()
        approval_mock.enqueue_approve_confirmation.assert_not_called()

    def test_no_dispara_si_confirmation_id_ya_estaba(self):
        frappe_mock = MagicMock()
        doc = self._doc(confirmation_id="00001", before_confirmation_id="00001")

        with patch.object(mod, "frappe", frappe_mock), \
             patch.object(mod, "approval") as approval_mock:
            mod.on_purchase_invoice_bc_update(doc, "on_update")

        frappe_mock.db.set_value.assert_not_called()
        approval_mock.enqueue_approve_confirmation.assert_not_called()

    def test_no_dispara_si_no_existe_documentdetail(self):
        frappe_mock = MagicMock()
        frappe_mock.db.exists.return_value = None
        doc = self._doc(confirmation_id="00001", before_confirmation_id=None)

        with patch.object(mod, "frappe", frappe_mock), \
             patch.object(mod, "approval") as approval_mock:
            mod.on_purchase_invoice_bc_update(doc, "on_update")

        frappe_mock.db.set_value.assert_not_called()
        approval_mock.enqueue_approve_confirmation.assert_not_called()

    def test_no_dispara_si_no_tiene_purchase_invoice(self):
        frappe_mock = MagicMock()
        doc = self._doc(confirmation_id="00001", before_confirmation_id=None,
                        purchase_invoice=None)

        with patch.object(mod, "frappe", frappe_mock), \
             patch.object(mod, "approval") as approval_mock:
            mod.on_purchase_invoice_bc_update(doc, "on_update")

        frappe_mock.db.set_value.assert_not_called()
        approval_mock.enqueue_approve_confirmation.assert_not_called()

    def test_error_no_rompe_y_loguea(self):
        frappe_mock = MagicMock()
        frappe_mock.db.exists.return_value = 1
        frappe_mock.db.set_value.side_effect = Exception("boom")
        doc = self._doc(confirmation_id="00001", before_confirmation_id=None)

        with patch.object(mod, "frappe", frappe_mock), \
             patch.object(mod, "approval") as approval_mock:
            mod.on_purchase_invoice_bc_update(doc, "on_update")

        frappe_mock.db.rollback.assert_called_once()
        frappe_mock.log_error.assert_called_once()
        approval_mock.enqueue_approve_confirmation.assert_not_called()


if __name__ == "__main__":
    unittest.main()
