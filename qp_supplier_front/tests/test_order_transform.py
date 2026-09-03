# -*- coding: utf-8 -*-
"""
test_order_transform.py
========================
Pruebas unitarias para infrastructure/strategies/gp/order_transform.py
Verifica el mapeo de campos API GP -> tuplas DB (mismo comportamiento
que uses_cases/sales_order/sync_by_supplier.py original).
Aisladas de Frappe y de la base de datos.
Ejecutar con: python -m unittest qp_supplier_front.tests.test_order_transform -v
"""
import unittest
from datetime import datetime

from qp_supplier_front.infrastructure.strategies.gp.order_transform import (
    build_order_records,
)


def make_strategy():
    return {
        "request_key_id": "orderId",
        "request_list_key": "products",
        "request_list_key_id": "itemnmbr",
        "doctype": "Purchase Order",
    }


def make_order(products=None):
    return {
        "orderId": "OC-1",
        "vendor": "SUP-1",
        "docDate": "2026-01-01",
        "prmDate": "2026-02-01",
        "products": products if products is not None else [
            {
                "itemnmbr": "ITM-1",
                "qtyOrder": 5,
                "unitCost": 100,
                "extdCost": "500",
            }
        ],
    }


class TestBuildOrderRecords(unittest.TestCase):

    def setUp(self):
        self.now = datetime(2026, 8, 6, 12, 0, 0)
        self.company = "ACME"

    def test_doc_tuple_mapping(self):
        strategy = make_strategy()
        docs, items, errors, doc_errors = build_order_records(
            [make_order()], {}, self.now, self.company, strategy
        )
        self.assertEqual(len(docs), 1)
        doc = docs["OC-1:SUP-1"]
        self.assertEqual(doc[0], "OC-1:SUP-1")
        self.assertEqual(doc[1], "OC-1")
        self.assertEqual(doc[2], "2026-01-01")
        self.assertEqual(doc[3], "SUP-1")
        self.assertEqual(doc[4], "2026-02-01")
        self.assertEqual(doc[5], "2026-01-01")
        self.assertEqual(doc[7], self.company)
        self.assertEqual(doc[10], "Administrator")
        self.assertEqual(doc[11], "Administrator")

    def test_item_tuple_mapping(self):
        strategy = make_strategy()
        docs, items, errors, doc_errors = build_order_records(
            [make_order()], {"ITM-1": {}}, self.now, self.company, strategy
        )
        self.assertEqual(len(items), 1)
        item = items["OC-1:SUP-1:ITM-1"]
        self.assertEqual(item[0], "OC-1:SUP-1:ITM-1")
        self.assertEqual(item[1], "ITM-1")
        self.assertEqual(item[2], 5)
        self.assertEqual(item[3], 1)
        self.assertEqual(item[4], 100)
        self.assertEqual(item[5], 100)
        self.assertEqual(item[6], "500")
        self.assertEqual(item[7], "OC-1:SUP-1")
        self.assertEqual(item[8], "items")
        self.assertEqual(item[9], "Purchase Order")
        self.assertEqual(item[10], "500")
        self.assertEqual(item[11], "")
        self.assertEqual(item[14], "Administrator")
        self.assertEqual(item[15], "Administrator")

    def test_item_name_lookup_preserved(self):
        # El comportamiento original devuelve "" porque la clave "item_name"
        # se busca sobre el dict de items validos (no sobre el item).
        strategy = make_strategy()
        docs, items, errors, doc_errors = build_order_records(
            [make_order()],
            {"ITM-1": {"item_code": "ITM-1", "item_name": "Producto A"}},
            self.now,
            self.company,
            strategy,
        )
        self.assertEqual(items["OC-1:SUP-1:ITM-1"][11], "")

    def test_product_not_found_adds_line_error(self):
        strategy = make_strategy()
        docs, items, errors, doc_errors = build_order_records(
            [make_order()], {}, self.now, self.company, strategy
        )
        self.assertEqual(len(items), 0)
        self.assertEqual(len(errors), 1)
        error = list(errors.values())[0]
        self.assertEqual(error[1], 1)
        self.assertEqual(error[2], "ITM-1")
        self.assertEqual(error[4], "OC-1:SUP-1")
        self.assertEqual(error[5], "lines_errors")
        self.assertEqual(error[6], "Purchase Order")
        # El documento se inserta igual aunque falle la linea
        self.assertEqual(len(docs), 1)

    def test_amount_too_long_adds_line_error(self):
        strategy = make_strategy()
        order = make_order(products=[{
            "itemnmbr": "ITM-1",
            "qtyOrder": 1,
            "unitCost": 1,
            "extdCost": "12345678901234567890",
        }])
        docs, items, errors, doc_errors = build_order_records(
            [order], {"ITM-1": {}}, self.now, self.company, strategy
        )
        self.assertEqual(len(items), 0)
        self.assertEqual(len(errors), 1)
        error = list(errors.values())[0]
        # El error generico se registra con code 0 (comportamiento original)
        self.assertEqual(error[2], 0)
        self.assertIn("monto", error[3])

    def test_order_without_products_logs_doc_error(self):
        strategy = make_strategy()
        docs, items, errors, doc_errors = build_order_records(
            [make_order(products=[])], {}, self.now, self.company, strategy
        )
        self.assertEqual(len(docs), 1)
        self.assertEqual(len(items), 0)
        self.assertEqual(len(doc_errors), 1)
        self.assertIn("OC-1", doc_errors[0]["title"])

    def test_valid_item_is_kept_and_unknown_skipped(self):
        strategy = make_strategy()
        order = make_order(products=[
            {"itemnmbr": "ITM-1", "qtyOrder": 1, "unitCost": 10, "extdCost": "10"},
            {"itemnmbr": "ITM-X", "qtyOrder": 2, "unitCost": 20, "extdCost": "40"},
        ])
        docs, items, errors, doc_errors = build_order_records(
            [order], {"ITM-1": {}}, self.now, self.company, strategy
        )
        self.assertIn("OC-1:SUP-1:ITM-1", items)
        self.assertNotIn("OC-1:SUP-1:ITM-X", items)
        self.assertEqual(len(errors), 1)


if __name__ == "__main__":
    unittest.main()
