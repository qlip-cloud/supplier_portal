# -*- coding: utf-8 -*-
"""
test_data_facade.py
===================
Pruebas del facade de datos documenteme
(infrastructure/adapters/data_facade.py): modo memory (store) y modo real
(delegacion a frappe).

Ejecutar con: python -m pytest qp_supplier_front/tests/test_data_facade.py -v
"""
import unittest
from unittest.mock import MagicMock, patch

from qp_supplier_front.infrastructure.adapters.data_facade import DataFacade, MemDoc
from qp_supplier_front.simulation.store import MemoryStore

SIM_NIT = "999999999"


class TestMemoryFacade(unittest.TestCase):

    def setUp(self):
        self.store = MemoryStore()
        self.facade = DataFacade(store=self.store)
        self.store.insert("qp_SP_DocumentDetail", {
            "name": "999999999:F1", "nvfac_esta": "E", "nvpro_ndoc": SIM_NIT,
        })

    def test_get_doc_del_store(self):
        doc = self.facade.get_doc("qp_SP_DocumentDetail", "999999999:F1")
        self.assertIsInstance(doc, MemDoc)
        self.assertEqual(doc.get("nvfac_esta"), "E")
        self.assertEqual(doc.name, "999999999:F1")

    def test_get_doc_set_y_save(self):
        doc = self.facade.get_doc("qp_SP_DocumentDetail", "999999999:F1")
        doc.nvfac_esta = "V"
        doc.save()
        self.assertEqual(self.store.get("qp_SP_DocumentDetail", "999999999:F1")["nvfac_esta"], "V")

    def test_get_doc_nuevo_y_save(self):
        doc = self.facade.get_doc({
            "doctype": "qp_SP_PurchaseInvoiceBC",
            "invoice_id": "SIMF1",
            "purchase_invoice": "999999999:F1",
        })
        doc.insert = None
        doc.save()
        rows = self.store.query("qp_SP_PurchaseInvoiceBC")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["invoice_id"], "SIMF1")

    def test_get_all(self):
        rows = self.facade.get_all("qp_SP_DocumentDetail",
                                   filters={"nvfac_esta": "E"}, fields=["name"])
        self.assertEqual(len(rows), 1)

    def test_get_all_pluck(self):
        rows = self.facade.get_all("qp_SP_DocumentDetail", pluck="name")
        self.assertEqual(rows, ["999999999:F1"])

    def test_exists(self):
        self.assertTrue(self.facade.exists("qp_SP_DocumentDetail", {"nvpro_ndoc": SIM_NIT}))
        self.assertFalse(self.facade.exists("qp_SP_DocumentDetail", "X"))

    def test_set_value(self):
        self.facade.set_value("qp_SP_DocumentDetail", "999999999:F1", "nvfac_esta", "R")
        self.assertEqual(self.store.get("qp_SP_DocumentDetail", "999999999:F1")["nvfac_esta"], "R")

    def test_set_value_dict(self):
        self.facade.set_value("qp_SP_DocumentDetail", "999999999:F1",
                              {"nvfac_esta": "A", "nvfac_ueve": "033"})
        row = self.store.get("qp_SP_DocumentDetail", "999999999:F1")
        self.assertEqual(row["nvfac_esta"], "A")
        self.assertEqual(row["nvfac_ueve"], "033")

    def test_child_append_y_save(self):
        doc = self.facade.get_doc("qp_SP_DocumentDetail", "999999999:F1")
        log = doc.append("qp_SP_EventLog")
        log.event_code = "031"
        log.response = "{}"
        log.status = 200
        doc.save()
        rows = self.store.query("qp_SP_EventLog", filters={"parent": "999999999:F1"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_code"], "031")

    def test_insert_child(self):
        self.facade.insert_child("qp_SP_Alert", "999999999:F1", {"message": "x"})
        rows = self.store.query("qp_SP_Alert", filters={"parent": "999999999:F1"})
        self.assertEqual(len(rows), 1)

    def test_delete_doc(self):
        self.facade.delete_doc("qp_SP_DocumentDetail", "999999999:F1")
        self.assertFalse(self.store.exists("qp_SP_DocumentDetail", "999999999:F1"))

    def test_referencias_leer_del_store(self):
        # Las referencias no delegadas a frappe: se leen del store (seeds).
        facade = DataFacade(store=self.store)
        self.assertFalse(facade.exists("Purchase Order", "PO-1"))
        self.assertIsNone(facade.get_value("User", "u@x", "full_name"))
        seed_store = MemoryStore()
        seed_store.insert("User", {"name": "u@x", "full_name": "Ana"})
        self.assertEqual(
            DataFacade(store=seed_store).get_value("User", "u@x", "full_name"),
            "Ana")


class TestRealFacade(unittest.TestCase):

    def test_delega_get_all(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = [{"name": "D1"}]
        facade = DataFacade(frappe=frappe_mock)
        rows = facade.get_all("qp_SP_DocumentDetail", filters={"nvfac_esta": "E"})
        frappe_mock.get_all.assert_called_once()
        self.assertEqual(rows, [{"name": "D1"}])

    def test_get_all_reenvia_pluck(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = ["D1", "D2"]
        facade = DataFacade(frappe=frappe_mock)
        result = facade.get_all(
            "qp_SP_DocumentDetail", filters={"nvfac_esta": "V"},
            pluck="name")
        self.assertEqual(result, ["D1", "D2"])
        assert_kwargs = frappe_mock.get_all.call_args[1]
        self.assertEqual(assert_kwargs["pluck"], "name")
        self.assertEqual(assert_kwargs["start"], 0)
        self.assertIsNone(assert_kwargs["page_length"])

    def test_get_all_reenvia_paginacion(self):
        frappe_mock = MagicMock()
        facade = DataFacade(frappe=frappe_mock)
        facade.get_all("qp_SP_DocumentDetail", start=0, page_length=15)
        assert_kwargs = frappe_mock.get_all.call_args[1]
        self.assertEqual(assert_kwargs["start"], 0)
        self.assertEqual(assert_kwargs["page_length"], 15)

    def test_get_list_reenvia_pluck(self):
        frappe_mock = MagicMock()
        frappe_mock.get_list.return_value = ["X"]
        facade = DataFacade(frappe=frappe_mock)
        result = facade.get_list(
            "qp_SP_DocumentDetail", filters={"nvfac_esta": "V"}, pluck="name")
        self.assertEqual(result, ["X"])
        self.assertEqual(frappe_mock.get_list.call_args[1]["pluck"], "name")

    def test_get_v_doc_names_real_devuelve_strings(self):
        corrupt = {
            "name": "SETP990086901",
            "nvfac_esta": "V",
            "nvfac_nume": "SETP990086901",
        }
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = [corrupt]
        facade = DataFacade(frappe=frappe_mock)

        from qp_supplier_front.resources.documenteme import auto_approve
        with patch.object(auto_approve, "runtime") as rt:
            rt.resolve.return_value = {"data": facade, "approve_callbacks": {}}
            names = auto_approve.get_v_doc_names(["D1"])

        self.assertEqual(names, [corrupt])
        kwargs = frappe_mock.get_all.call_args[1]
        self.assertEqual(kwargs["pluck"], "name")

    def test_delega_set_value(self):
        frappe_mock = MagicMock()
        frappe_mock.db.set_value.return_value = True
        facade = DataFacade(frappe=frappe_mock)
        facade.set_value("qp_SP_DocumentDetail", "D1", "nvfac_esta", "E")
        frappe_mock.db.set_value.assert_called_once_with(
            "qp_SP_DocumentDetail", "D1", "nvfac_esta", "E")


if __name__ == "__main__":
    unittest.main()