# -*- coding: utf-8 -*-
"""
test_order_sync_core.py
========================
Pruebas unitarias para uses_cases/purchase_order/sync_core.py
(sincronizacion de ordenes por ventanas).
Aisladas de Frappe y de la base de datos.
Ejecutar con: python -m unittest qp_supplier_front.tests.test_order_sync_core -v
"""
import unittest
from datetime import datetime

from qp_supplier_front.uses_cases.purchase_order.sync_core import sync_orders_window
from qp_supplier_front.exception.sync import ExceptionSyncResponseEmpty


def build_strategy(transform=None):
    def default_transform(orders_data, items_valid, now, company, strategy):
        docs = {}
        for order in orders_data:
            docs[order["orderId"]] = (order["orderId"], now)
        return docs, {}, {}, []

    return {
        "name": "GP",
        "endpoints": {"per_supplier_range": "order_supplier_date_range"},
        "db_fields": {
            "id_field": "qp_order_id",
            "order_field": "qp_create_date",
            "supplier_field": "supplier",
        },
        "doctype": "Purchase Order",
        "request_key": "orders",
        "request_key_id": "orderId",
        "request_list_key": "products",
        "request_list_key_id": "itemnmbr",
        "build_param": lambda s, ws, we: "{}/{}/{}".format(s, ws, we),
        "transform": transform or default_transform,
        "persist": {
            "insert_orders": lambda docs, now: None,
            "insert_items": lambda items, now: None,
            "insert_errors": lambda errors, now: None,
        },
    }


def make_captures():
    captures = {
        "logs": [],
        "commits": [],
        "errors": [],
        "items_calls": [],
        "company_calls": [],
        "fetch_calls": [],
    }
    return captures


def run_window(
    captures,
    fetch_result,
    existing_ids=None,
    transform=None,
    last_creation_fn=None,
):
    strategy = build_strategy(transform)

    def fetch_fn(endpoint, param=None):
        captures["fetch_calls"].append((endpoint, param))
        return fetch_result

    def existing_ids_fn(doctype, id_field, candidate_ids=None):
        return set(existing_ids or [])

    def get_items_fn():
        captures["items_calls"].append(True)
        return {}

    def get_company_fn():
        captures["company_calls"].append(True)
        return "ACME"

    def commit_fn():
        captures["commits"].append(True)

    def log_sync_fn(**kwargs):
        captures["logs"].append(kwargs)

    def log_error_fn(message, title):
        captures["errors"].append((message, title))

    return sync_orders_window(
        supplier_id="SUP-1",
        window_start=datetime(2024, 1, 1),
        window_end=datetime(2024, 1, 31),
        now=datetime(2026, 8, 6, 12, 0, 0),
        strategy=strategy,
        fetch_fn=fetch_fn,
        existing_ids_fn=existing_ids_fn,
        get_items_fn=get_items_fn,
        get_company_fn=get_company_fn,
        commit_fn=commit_fn,
        log_sync_fn=log_sync_fn,
        log_error_fn=log_error_fn,
    )


class TestSyncOrdersWindowHappyPath(unittest.TestCase):

    def setUp(self):
        self.captures = make_captures()
        self.orders = [
            {"orderId": "OC-1", "vendor": "SUP-1", "products": []},
            {"orderId": "OC-2", "vendor": "SUP-1", "products": []},
        ]

    def test_success_inserts_only_new_and_logs(self):
        result = run_window(
            self.captures,
            {"orders": self.orders},
            existing_ids=[],
        )
        self.assertEqual(result["status"], "Success")
        self.assertEqual(result["found"], 2)
        self.assertEqual(result["inserted"], 2)
        self.assertEqual(result["skipped"], 0)
        self.assertTrue(self.captures["commits"])
        self.assertEqual(self.captures["logs"][0]["status"], "In Progress")
        self.assertEqual(self.captures["logs"][-1]["status"], "Success")
        self.assertEqual(self.captures["logs"][-1]["records_inserted"], 2)
        self.assertEqual(len(self.captures["items_calls"]), 1)
        self.assertEqual(len(self.captures["company_calls"]), 1)

    def test_fetch_receives_range_endpoint_and_param(self):
        run_window(self.captures, {"orders": self.orders})
        endpoint, param = self.captures["fetch_calls"][0]
        self.assertEqual(endpoint, "order_supplier_date_range")
        self.assertIn("SUP-1", param)

    def test_existing_orders_are_skipped(self):
        result = run_window(
            self.captures,
            {"orders": self.orders},
            existing_ids=["OC-1"],
        )
        self.assertEqual(result["status"], "Success")
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(result["skipped"], 1)

    def test_all_existing_returns_no_new_records(self):
        result = run_window(
            self.captures,
            {"orders": self.orders},
            existing_ids=["OC-1", "OC-2"],
        )
        self.assertEqual(result["status"], "NoNewRecords")
        self.assertEqual(result["inserted"], 0)
        self.assertEqual(self.captures["logs"][-1]["status"], "NoNewRecords")
        self.assertTrue(self.captures["commits"])


class TestSyncOrdersWindowEmptyAndMalformed(unittest.TestCase):

    def setUp(self):
        self.captures = make_captures()

    def test_empty_orders_list_is_no_new_records(self):
        result = run_window(self.captures, {"orders": []})
        self.assertEqual(result["status"], "NoNewRecords")
        self.assertEqual(result["found"], 0)
        self.assertEqual(result["inserted"], 0)
        self.assertTrue(self.captures["commits"])
        self.assertEqual(self.captures["logs"][-1]["status"], "NoNewRecords")

    def test_missing_request_key_raises(self):
        with self.assertRaises(ExceptionSyncResponseEmpty):
            run_window(self.captures, {"other": []})


class TestSyncOrdersWindowDocErrors(unittest.TestCase):

    def test_transform_doc_errors_are_logged(self):
        captures = make_captures()

        def transform_with_errors(orders_data, items_valid, now, company, strategy):
            docs = {o["orderId"]: (o["orderId"], now) for o in orders_data}
            return docs, {}, {}, [{"title": "Sin lineas", "message": "{}"}]

        result = run_window(
            captures,
            {"orders": [{"orderId": "OC-1", "vendor": "SUP-1"}]},
            transform=transform_with_errors,
        )
        self.assertEqual(result["status"], "Success")
        self.assertEqual(result["inserted"], 1)
        self.assertEqual(len(captures["errors"]), 1)
        self.assertEqual(captures["errors"][0][1], "Sin lineas")


if __name__ == "__main__":
    unittest.main()
