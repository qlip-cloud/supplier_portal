# -*- coding: utf-8 -*-
"""
test_invoice_sync_core.py
==========================
Pruebas unitarias para uses_cases/purchase_invoice/sync_core.py
(sync_invoices_window).
Aisladas de Frappe y de la base de datos.
Ejecutar con: python -m unittest qp_supplier_front.tests.test_invoice_sync_core -v
"""
import unittest
from datetime import datetime

import qp_supplier_front.uses_cases.purchase_invoice.sync_core as core
from qp_supplier_front.exception.sync import ExceptionSyncResponseEmpty


def build_strategy(filter_fn=None, transform=None):
    def default_transform(invoices_data, strategy_name, now):
        return {
            inv["invoiceId"]: (inv["invoiceId"], now)
            for inv in invoices_data
        }

    return {
        "name": "GP",
        "endpoints": {
            "per_supplier_range": "invoice_supplier_date_range",
            "all_range": "invoice_all_range",
        },
        "db_fields": {
            "id_field": "invoice_id",
            "order_field": "create_date",
        },
        "doctype": "qp_SP_PurchaseInvoice",
        "request_key": "invoices",
        "request_key_id": "invoiceId",
        "build_param": lambda s, last_date=None, now=None: "{}/{}/{}".format(
            s, last_date, now
        ),
        "build_all_range_param": lambda ws, we: "$filter=Posting_Date ge {} and Posting_Date le {}".format(
            ws, we
        ),
        "filter": filter_fn or (lambda data, max_length=140: (data, [])),
        "transform": transform or default_transform,
        "persist": {
            "insert_invoices": lambda docs, now: None,
        },
    }


def run_window(
    captures,
    fetch_result,
    existing_ids=None,
    filter_fn=None,
    transform=None,
    log_skipped_fn=None,
    scope="supplier",
):
    strategy = build_strategy(filter_fn, transform)

    original = core.get_strategy
    core.get_strategy = lambda flow: strategy

    try:
        def fetch_fn(endpoint, param=None):
            captures["fetch_calls"].append((endpoint, param))
            return fetch_result

        def existing_ids_fn(doctype, id_field, candidate_ids=None):
            return set(existing_ids or [])

        def commit_fn():
            captures["commits"].append(True)

        def log_sync_fn(**kwargs):
            captures["logs"].append(kwargs)

        return core.sync_invoices_window(
            supplier_id="SUP-1",
            flow="BC",
            window_start=datetime(2024, 1, 1),
            window_end=datetime(2024, 1, 31),
            fetch_fn=fetch_fn,
            existing_ids_fn=existing_ids_fn,
            commit_fn=commit_fn,
            log_sync_fn=log_sync_fn,
            now=datetime(2026, 8, 6, 12, 0, 0),
            log_skipped_fn=log_skipped_fn,
            scope=scope,
        )
    finally:
        core.get_strategy = original


def make_captures():
    return {
        "logs": [],
        "commits": [],
        "fetch_calls": [],
    }


class TestSyncInvoicesWindowHappyPath(unittest.TestCase):

    def setUp(self):
        self.captures = make_captures()
        self.invoices = [
            {"invoiceId": "INV-1", "vendor": "SUP-1"},
            {"invoiceId": "INV-2", "vendor": "SUP-1"},
        ]

    def test_success_inserts_and_logs(self):
        result = run_window(self.captures, {"invoices": self.invoices})
        self.assertEqual(result["status"], "Success")
        self.assertEqual(result["found"], 2)
        self.assertEqual(result["inserted"], 2)
        self.assertEqual(result["skipped"], 0)
        self.assertTrue(self.captures["commits"])
        self.assertEqual(self.captures["logs"][0]["status"], "In Progress")
        self.assertEqual(self.captures["logs"][-1]["status"], "Success")
        self.assertEqual(self.captures["logs"][-1]["records_inserted"], 2)

    def test_fetch_uses_range_endpoint(self):
        run_window(self.captures, {"invoices": self.invoices})
        endpoint, param = self.captures["fetch_calls"][0]
        self.assertEqual(endpoint, "invoice_supplier_date_range")
        self.assertIn("SUP-1", param)

    def test_existing_invoices_skipped(self):
        result = run_window(
            self.captures,
            {"invoices": self.invoices},
            existing_ids=["INV-1"],
        )
        self.assertEqual(result["status"], "Success")
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["skipped"], 1)


class TestSyncInvoicesWindowFilter(unittest.TestCase):

    def test_skipped_records_are_logged(self):
        captures = make_captures()
        skipped_called = []

        def filter_fn(invoices_data, max_length=140):
            return [], [{"Document_No": "INV-1"}]

        result = run_window(
            captures,
            {"invoices": [{"invoiceId": "INV-1", "vendor": "SUP-1"}]},
            filter_fn=filter_fn,
            log_skipped_fn=lambda skip: skipped_called.append(skip),
        )
        self.assertEqual(result["status"], "NoNewRecords")
        self.assertEqual(len(skipped_called), 1)


class TestSyncInvoicesWindowGlobalScope(unittest.TestCase):

    def setUp(self):
        self.captures = make_captures()

    def test_global_uses_all_range_endpoint_without_supplier(self):
        result = run_window(
            self.captures,
            {"invoices": [{"invoiceId": "INV-1", "vendor": "V-1"}]},
            scope="global",
        )
        endpoint, param = self.captures["fetch_calls"][0]
        self.assertEqual(endpoint, "invoice_all_range")
        self.assertIn("Posting_Date", param)
        self.assertNotIn("Vendor", param)
        self.assertEqual(result["status"], "Success")
        self.assertEqual(result["inserted"], 1)

    def test_global_dedups_existing(self):
        result = run_window(
            self.captures,
            {"invoices": [{"invoiceId": "INV-1", "vendor": "V-1"}]},
            existing_ids=["INV-1"],
            scope="global",
        )
        self.assertEqual(result["status"], "NoNewRecords")
        self.assertEqual(result["inserted"], 0)


class TestSyncInvoicesWindowEmptyAndMalformed(unittest.TestCase):

    def setUp(self):
        self.captures = make_captures()

    def test_empty_invoices_is_no_new_records(self):
        result = run_window(self.captures, {"invoices": []})
        self.assertEqual(result["status"], "NoNewRecords")
        self.assertEqual(result["inserted"], 0)
        self.assertEqual(self.captures["logs"][-1]["status"], "NoNewRecords")
        self.assertTrue(self.captures["commits"])

    def test_all_existing_returns_no_new_records(self):
        result = run_window(
            self.captures,
            {"invoices": [{"invoiceId": "INV-1", "vendor": "SUP-1"}]},
            existing_ids=["INV-1"],
        )
        self.assertEqual(result["status"], "NoNewRecords")
        self.assertEqual(result["inserted"], 0)

    def test_missing_request_key_raises(self):
        with self.assertRaises(ExceptionSyncResponseEmpty):
            run_window(self.captures, {"other": []})


class TestSyncInvoicesWindowLoggingSafety(unittest.TestCase):

    def test_logging_failure_does_not_break_sync(self):
        captures = make_captures()
        strategy = build_strategy()
        original = core.get_strategy
        core.get_strategy = lambda flow: strategy

        try:
            def fetch_fn(endpoint, param=None):
                return {"invoices": [{"invoiceId": "INV-1", "vendor": "SUP-1"}]}

            def existing_ids_fn(doctype, id_field, candidate_ids=None):
                return set()

            def commit_fn():
                captures["commits"].append(True)

            def failing_log_sync_fn(**kwargs):
                raise OSError("log insert failed")

            result = core.sync_invoices_window(
                supplier_id="SUP-1",
                flow="GP",
                window_start=datetime(2024, 1, 1),
                window_end=datetime(2024, 1, 31),
                fetch_fn=fetch_fn,
                existing_ids_fn=existing_ids_fn,
                commit_fn=commit_fn,
                log_sync_fn=failing_log_sync_fn,
                now=datetime(2026, 8, 6, 12, 0, 0),
            )
            self.assertEqual(result["status"], "Success")
            self.assertEqual(result["inserted"], 1)
            self.assertTrue(captures["commits"])
        finally:
            core.get_strategy = original


if __name__ == "__main__":
    unittest.main()
