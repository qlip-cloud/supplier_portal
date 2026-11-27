# -*- coding: utf-8 -*-
"""
test_inbound_api_log.py
=======================
Pruebas unitarias para services/inbound_api_log.py (log de requests de API a
archivo, un archivo por doctype).
Aisladas de Frappe y del filesystem (se mockea ``_emit``).
Ejecutar con: python -m unittest qp_supplier_front.tests.test_inbound_api_log -v
"""
import importlib
import json
import sys
import unittest
from unittest import mock

from qp_supplier_front import hooks
from qp_supplier_front.services import inbound_api_log

HOOK_PATH = (
    "qp_supplier_front.services.inbound_api_log.log_inbound_api_request"
)


class TestIsApiRequest(unittest.TestCase):

    def test_api_path_is_logged(self):
        self.assertTrue(
            inbound_api_log.is_api_request("/api/resource/Purchase Order")
        )

    def test_non_api_path_is_skipped(self):
        self.assertFalse(inbound_api_log.is_api_request("/purchase_order"))
        self.assertFalse(inbound_api_log.is_api_request("/api"))
        self.assertFalse(inbound_api_log.is_api_request(None))


class TestBuildLogRecord(unittest.TestCase):

    def test_maps_fields(self):
        record = inbound_api_log.build_log_record(
            doctype="Purchase Order",
            response={"name": "PO-0001"},
            name="PO-0001",
            supplier="SUP-1",
            path="/api/resource/Purchase Order",
            raw_body='{"a": 1}',
            status_code=200,
            event="created",
            origin="api",
            user="api@example.com",
            ip="10.0.0.1",
            method="POST",
        )

        self.assertEqual(record["event"], "created")
        self.assertEqual(record["doctype"], "Purchase Order")
        self.assertEqual(record["name"], "PO-0001")
        self.assertEqual(record["supplier"], "SUP-1")
        self.assertEqual(record["status_code"], 200)
        self.assertEqual(record["origin"], "api")
        self.assertEqual(record["payload"], '{"a": 1}')
        self.assertEqual(record["response"], {"name": "PO-0001"})

    def test_serializes_as_single_line(self):
        record = inbound_api_log.build_log_record(
            doctype="Purchase Order",
            response={},
            raw_body="linea 1\nlinea 2",
        )

        line = json.dumps(record, default=str, ensure_ascii=False)

        self.assertNotIn("\n", line)


class _FakeRequest(object):

    def __init__(self, path="/api/resource/Purchase Order", body='{"a": 1}',
                 headers=None, method="POST"):
        self.path = path
        self._body = body
        self.headers = headers or {}
        self.method = method

    def get_data(self, as_text=False):
        return self._body


class _FakeDoc(object):

    def __init__(self, doctype="Purchase Order", name="PO-0001",
                 supplier="SUP-1"):
        self.doctype = doctype
        self.name = name
        self.supplier = supplier

    def as_dict(self):
        return {
            "name": self.name,
            "doctype": self.doctype,
            "supplier": self.supplier,
        }

    def get(self, fieldname, default=None):
        return getattr(self, fieldname, default)


class _FakeLinkError(Exception):

    http_status_code = 417


class _LogTestBase(unittest.TestCase):

    def setUp(self):
        self.frappe = mock.MagicMock()
        self.frappe.local.response = {}
        self.frappe.local.request_ip = "10.0.0.1"
        self.frappe.session.user = "api@example.com"
        self.modules = mock.patch.dict(sys.modules, {"frappe": self.frappe})
        self.modules.start()
        self.addCleanup(self.modules.stop)

        self.emit = mock.MagicMock()
        self.emit_patch = mock.patch.object(
            inbound_api_log, "_emit", self.emit
        )
        self.emit_patch.start()
        self.addCleanup(self.emit_patch.stop)

    def last_module(self):
        return self.emit.call_args[0][0]

    def last_record(self):
        line = self.emit.call_args[0][1]
        return json.loads(line)


class TestLogCreated(_LogTestBase):

    def test_logs_to_purchase_order_file(self):
        self.frappe.local.request = _FakeRequest()

        inbound_api_log.log_inbound_api_request(_FakeDoc())

        self.assertEqual(self.last_module(), "inbound_purchase_order")
        record = self.last_record()

        self.assertEqual(record["event"], "created")
        self.assertEqual(record["doctype"], "Purchase Order")
        self.assertEqual(record["name"], "PO-0001")
        self.assertEqual(record["supplier"], "SUP-1")
        self.assertEqual(record["status_code"], 200)
        self.assertEqual(record["origin"], "api")
        self.assertEqual(record["user"], "api@example.com")
        self.assertEqual(record["ip"], "10.0.0.1")
        self.assertEqual(record["payload"], '{"a": 1}')
        self.assertEqual(record["response"]["name"], "PO-0001")

    def test_logs_to_purchase_receipt_file(self):
        self.frappe.local.request = _FakeRequest(
            path="/api/resource/Purchase Receipt"
        )

        inbound_api_log.log_inbound_api_request(
            _FakeDoc(doctype="Purchase Receipt", name="PR-0001")
        )

        self.assertEqual(self.last_module(), "inbound_purchase_receipt")
        self.assertEqual(self.last_record()["event"], "created")

    def test_marks_desk_origin_when_csrf_present(self):
        self.frappe.local.request = _FakeRequest(
            headers={"X-Frappe-CSRF-Token": "abc"}
        )

        inbound_api_log.log_inbound_api_request(_FakeDoc())

        self.assertEqual(self.last_record()["origin"], "desk")

    def test_skips_non_api_path(self):
        self.frappe.local.request = _FakeRequest(path="/purchase_order")

        inbound_api_log.log_inbound_api_request(_FakeDoc())

        self.emit.assert_not_called()

    def test_skips_when_there_is_no_request(self):
        self.frappe.local.request = None

        inbound_api_log.log_inbound_api_request(_FakeDoc())

        self.emit.assert_not_called()

    def test_write_failure_is_swallowed(self):
        self.frappe.local.request = _FakeRequest()
        self.emit.side_effect = Exception("disk")

        with mock.patch.object(inbound_api_log, "_log_failure") as failure:
            inbound_api_log.log_inbound_api_request(_FakeDoc())

        failure.assert_called_once()


class TestLogFailed(_LogTestBase):

    def test_logs_error_status_and_message(self):
        self.frappe.local.request = _FakeRequest()

        inbound_api_log.log_failed_api_request(
            _FakeDoc(), _FakeLinkError("Could not find Row #1: UOM: SX")
        )

        self.assertEqual(self.last_module(), "inbound_purchase_order")
        record = self.last_record()

        self.assertEqual(record["event"], "failed")
        self.assertEqual(record["status_code"], 417)
        self.assertEqual(record["payload"], '{"a": 1}')
        self.assertEqual(record["supplier"], "SUP-1")
        self.assertEqual(record["response"]["exc_type"], "_FakeLinkError")
        self.assertIn("UOM: SX", record["response"]["message"])

    def test_generic_error_uses_500(self):
        self.frappe.local.request = _FakeRequest()

        inbound_api_log.log_failed_api_request(_FakeDoc(), ValueError("boom"))

        self.assertEqual(self.last_record()["status_code"], 500)

    def test_failed_receipt_uses_receipt_file(self):
        self.frappe.local.request = _FakeRequest(
            path="/api/resource/Purchase Receipt"
        )

        inbound_api_log.log_failed_api_request(
            _FakeDoc(doctype="Purchase Receipt", name="PR-0001"),
            _FakeLinkError("boom"),
        )

        self.assertEqual(self.last_module(), "inbound_purchase_receipt")

    def test_skips_non_api_path(self):
        self.frappe.local.request = _FakeRequest(path="/purchase_order")

        inbound_api_log.log_failed_api_request(
            _FakeDoc(), _FakeLinkError("boom")
        )

        self.emit.assert_not_called()


class TestHookWiring(unittest.TestCase):

    def test_purchase_order_logs_api_creations(self):
        self.assertEqual(
            hooks.doc_events["Purchase Order"]["after_insert"], HOOK_PATH
        )

    def test_purchase_receipt_keeps_existing_trigger_and_logs(self):
        after_insert = hooks.doc_events["Purchase Receipt"]["after_insert"]

        self.assertIn(
            "qp_supplier_front.resources.documenteme.receipt_trigger.on_receipt_created",
            after_insert,
        )
        self.assertIn(HOOK_PATH, after_insert)

    def test_controlled_doctypes_override_controllers(self):
        self.assertEqual(
            hooks.override_doctype_class["Purchase Order"],
            "qp_supplier_front.overrides.purchase_order.QpPurchaseOrder",
        )
        self.assertEqual(
            hooks.override_doctype_class["Purchase Receipt"],
            "qp_supplier_front.overrides.purchase_receipt.QpPurchaseReceipt",
        )

    def test_hook_targets_resolve(self):
        paths = [
            HOOK_PATH,
            "qp_supplier_front.resources.documenteme.receipt_trigger.on_receipt_created",
        ]

        for path in paths:
            module_path, func_name = path.rsplit(".", 1)
            module = importlib.import_module(module_path)

            self.assertTrue(callable(getattr(module, func_name)))


if __name__ == "__main__":
    unittest.main()
