# -*- coding: utf-8 -*-
"""
test_receipt_sync_core.py
==========================
Pruebas unitarias para uses_cases/payment_receipt/sync_core.py
(sync_payments_window).
Aisladas de Frappe y de la base de datos.
Ejecutar con: python -m unittest qp_supplier_front.tests.test_receipt_sync_core -v
"""
import unittest
from datetime import datetime

import qp_supplier_front.uses_cases.payment_receipt.sync_core as core
from qp_supplier_front.exception.sync import ExceptionSyncResponseEmpty


def build_strategy(transform=None):
    def default_transform(payments_data, strategy_name, now):
        docs = {}
        items = {}
        for payment in payments_data:
            doc_id = payment["vchrnmbr"] + ":" + payment["vendor"]
            docs[doc_id] = (doc_id, now)
            for ref in (payment.get("reference") or []):
                item_id = doc_id + ":" + ref["aptvchnm"]
                items[item_id] = (item_id, doc_id)
        return docs, items

    return {
        "name": "GP",
        "endpoints": {
            "per_supplier_range": "payment_supplier_date_range",
            "all_range": "payment_all_range",
        },
        "db_fields": {
            "id_field": "qp_receipt_id",
            "order_field": "qp_posting_date",
        },
        "doctype": "qp_SP_PaymentReceipt",
        "request_key": "payments",
        "request_key_id": "vchrnmbr",
        "build_param": lambda s, last_date=None, now=None: "{}/{}/{}".format(
            s, last_date, now
        ),
        "build_all_range_param": lambda ws, we: "$filter=Posting_Date ge {} and Posting_Date le {}".format(
            ws, we
        ),
        "transform": transform or default_transform,
        "persist": {
            "insert_payments": lambda docs, now: None,
            "insert_items": lambda items, now: None,
        },
    }


def run_window(
    captures,
    fetch_result,
    existing_ids=None,
    transform=None,
    scope="supplier",
):
    strategy = build_strategy(transform)

    original = core.get_payment_strategy
    core.get_payment_strategy = lambda flow: strategy

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

        return core.sync_payments_window(
            supplier_id="SUP-1",
            flow="BC",
            window_start=datetime(2024, 1, 1),
            window_end=datetime(2024, 1, 31),
            fetch_fn=fetch_fn,
            existing_ids_fn=existing_ids_fn,
            commit_fn=commit_fn,
            log_sync_fn=log_sync_fn,
            now=datetime(2026, 8, 6, 12, 0, 0),
            scope=scope,
        )
    finally:
        core.get_payment_strategy = original


def make_captures():
    return {
        "logs": [],
        "commits": [],
        "fetch_calls": [],
    }


class TestSyncPaymentsWindowHappyPath(unittest.TestCase):

    def setUp(self):
        self.captures = make_captures()
        self.payments = [
            {"vchrnmbr": "P-1", "vendor": "SUP-1", "reference": []},
            {"vchrnmbr": "P-2", "vendor": "SUP-1", "reference": []},
        ]

    def test_success_inserts_and_logs(self):
        result = run_window(self.captures, {"payments": self.payments})
        self.assertEqual(result["status"], "Success")
        self.assertEqual(result["found"], 2)
        self.assertEqual(result["inserted"], 2)
        self.assertEqual(result["skipped"], 0)
        self.assertTrue(self.captures["commits"])
        self.assertEqual(self.captures["logs"][0]["status"], "In Progress")
        self.assertEqual(self.captures["logs"][-1]["status"], "Success")
        self.assertEqual(self.captures["logs"][-1]["records_inserted"], 2)

    def test_fetch_uses_range_endpoint(self):
        run_window(self.captures, {"payments": self.payments})
        endpoint, param = self.captures["fetch_calls"][0]
        self.assertEqual(endpoint, "payment_supplier_date_range")
        self.assertIn("SUP-1", param)

    def test_existing_payments_skipped(self):
        result = run_window(
            self.captures,
            {"payments": self.payments},
            existing_ids=["P-1"],
        )
        self.assertEqual(result["status"], "Success")
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["skipped"], 1)

    def test_items_persisted_when_present(self):
        payments = [{
            "vchrnmbr": "P-1",
            "vendor": "SUP-1",
            "reference": [{"aptvchnm": "FAC-1"}, {"aptvchnm": "FAC-2"}],
        }]
        result = run_window(self.captures, {"payments": payments})
        self.assertEqual(result["inserted"], 1)


class TestSyncPaymentsWindowGlobalScope(unittest.TestCase):

    def setUp(self):
        self.captures = make_captures()

    def test_global_uses_all_range_endpoint_without_supplier(self):
        result = run_window(
            self.captures,
            {"payments": [{"vchrnmbr": "P-1", "vendor": "V-1"}]},
            scope="global",
        )
        endpoint, param = self.captures["fetch_calls"][0]
        self.assertEqual(endpoint, "payment_all_range")
        self.assertIn("Posting_Date", param)
        self.assertNotIn("Vendor", param)
        self.assertEqual(result["status"], "Success")
        self.assertEqual(result["inserted"], 1)

    def test_global_dedups_existing(self):
        result = run_window(
            self.captures,
            {"payments": [{"vchrnmbr": "P-1", "vendor": "V-1"}]},
            existing_ids=["P-1"],
            scope="global",
        )
        self.assertEqual(result["status"], "NoNewRecords")
        self.assertEqual(result["inserted"], 0)


class TestSyncPaymentsWindowEmptyAndMalformed(unittest.TestCase):

    def setUp(self):
        self.captures = make_captures()

    def test_empty_payments_is_no_new_records(self):
        result = run_window(self.captures, {"payments": []})
        self.assertEqual(result["status"], "NoNewRecords")
        self.assertEqual(result["inserted"], 0)
        self.assertEqual(self.captures["logs"][-1]["status"], "NoNewRecords")
        self.assertTrue(self.captures["commits"])

    def test_all_existing_returns_no_new_records(self):
        result = run_window(
            self.captures,
            {"payments": [{"vchrnmbr": "P-1", "vendor": "SUP-1"}]},
            existing_ids=["P-1"],
        )
        self.assertEqual(result["status"], "NoNewRecords")
        self.assertEqual(result["inserted"], 0)

    def test_missing_request_key_raises(self):
        with self.assertRaises(ExceptionSyncResponseEmpty):
            run_window(self.captures, {"other": []})


class TestSyncPaymentsWindowLoggingSafety(unittest.TestCase):

    def test_logging_failure_does_not_break_sync(self):
        captures = make_captures()
        strategy = build_strategy()
        original = core.get_payment_strategy
        core.get_payment_strategy = lambda flow: strategy

        try:
            def fetch_fn(endpoint, param=None):
                return {"payments": [{"vchrnmbr": "P-1", "vendor": "SUP-1"}]}

            def existing_ids_fn(doctype, id_field, candidate_ids=None):
                return set()

            def commit_fn():
                captures["commits"].append(True)

            def failing_log_sync_fn(**kwargs):
                raise OSError("log insert failed")

            result = core.sync_payments_window(
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
            core.get_payment_strategy = original


if __name__ == "__main__":
    unittest.main()
