# -*- coding: utf-8 -*-
import sys
import unittest
from unittest.mock import MagicMock, patch

from qp_supplier_front.resources.documenteme import receipt_trigger


class TestReceiptAutoApprove(unittest.TestCase):

    def _frappe(self):
        frappe_mock = MagicMock()
        frappe_mock.flags.in_import = False
        frappe_mock.flags.in_migrate = False
        frappe_mock.flags.in_patch = False
        frappe_mock.get_all.return_value = [
            {"name": "DOC1", "nvfac_orde": "48709, 48748"},
            {"name": "DOC2", "nvfac_orde": "48748"},
            {"name": "DOC3", "nvfac_orde": "148748"},
        ]
        return frappe_mock

    def _run(self, frappe_mock, doc):
        with patch.dict(sys.modules, {"frappe": frappe_mock}), \
                patch.object(receipt_trigger, "_auto_approve_enabled",
                             return_value=True):
            receipt_trigger.on_receipt_created(doc)

    def test_encola_facturas_de_la_oc_exacta(self):
        frappe_mock = self._frappe()
        self._run(frappe_mock, {"qp_supplier_oc": "48748"})

        frappe_mock.enqueue.assert_called_once()
        args, kwargs = frappe_mock.enqueue.call_args
        self.assertEqual(
            args[0],
            "qp_supplier_front.resources.documenteme.auto_approve.auto_approve_now",
        )
        self.assertEqual(kwargs["doc_names"], ["DOC1", "DOC2"])
        self.assertEqual(kwargs["queue"], "long")
        self.assertTrue(kwargs["enqueue_after_commit"])

    def test_ignora_recibo_sin_oc(self):
        frappe_mock = self._frappe()
        self._run(frappe_mock, {"qp_supplier_oc": None})

        frappe_mock.get_all.assert_not_called()
        frappe_mock.enqueue.assert_not_called()

    def test_ignora_si_auto_approve_esta_deshabilitado(self):
        frappe_mock = self._frappe()
        with patch.dict(sys.modules, {"frappe": frappe_mock}), \
                patch.object(receipt_trigger, "_auto_approve_enabled",
                             return_value=False):
            receipt_trigger.on_receipt_created({"qp_supplier_oc": "48748"})

        frappe_mock.get_all.assert_not_called()
        frappe_mock.enqueue.assert_not_called()

    def test_no_encola_si_no_hay_facturas_de_la_oc(self):
        frappe_mock = self._frappe()
        self._run(frappe_mock, {"qp_supplier_oc": "99999"})

        frappe_mock.enqueue.assert_not_called()

    def test_no_encola_en_import_migrate_o_patch(self):
        for flag in ("in_import", "in_migrate", "in_patch"):
            frappe_mock = self._frappe()
            setattr(frappe_mock.flags, flag, True)
            self._run(frappe_mock, {"qp_supplier_oc": "48748"})

            frappe_mock.get_all.assert_not_called()
            frappe_mock.enqueue.assert_not_called()


if __name__ == "__main__":
    unittest.main()
