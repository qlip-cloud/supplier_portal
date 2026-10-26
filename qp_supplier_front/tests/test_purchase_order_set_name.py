# -*- coding: utf-8 -*-
"""
test_purchase_order_set_name.py
================================
Pruebas unitarias del hook before_insert de Purchase Order.
Ejecutar con: python -m unittest qp_supplier_front.tests.test_purchase_order_set_name -v
"""
import unittest

from qp_supplier_front.uses_cases.purchase_order import set_name


class FakeItem(object):
    def __init__(self, rate=None, qp_unit_cost=None):
        self.rate = rate
        self.qp_unit_cost = qp_unit_cost


class FakeFlags(object):
    name_set = False


class FakeDoc(object):
    def __init__(self, is_new=True, order_confirmation_no=None, items=None,
                 transaction_date=None):
        self._is_new = is_new
        self.order_confirmation_no = order_confirmation_no
        self.transaction_date = transaction_date
        self.items = items or []
        self.flags = FakeFlags()

    def is_new(self):
        return self._is_new

    def get(self, key):
        return getattr(self, key, None)


class TestSetName(unittest.TestCase):

    def test_sets_header_fields_for_new_doc(self):
        doc = FakeDoc(order_confirmation_no="48967", transaction_date="2026-10-26")

        set_name(doc, None)

        self.assertEqual(doc.name, "48967")
        self.assertEqual(doc.qp_order_confirmation_no, "48967")
        self.assertEqual(doc.qp_order_id, "48967")
        self.assertEqual(doc.qp_create_date, "2026-10-26")
        self.assertTrue(doc.flags.name_set)

    def test_fills_empty_rate_from_qp_unit_cost(self):
        doc = FakeDoc(items=[
            FakeItem(rate=None, qp_unit_cost=1000),
            FakeItem(rate=0, qp_unit_cost=500),
        ])

        set_name(doc, None)

        self.assertEqual(doc.items[0].rate, 1000)
        self.assertEqual(doc.items[1].rate, 500)

    def test_keeps_rate_when_already_set(self):
        doc = FakeDoc(items=[FakeItem(rate=3666.67, qp_unit_cost=1000)])

        set_name(doc, None)

        self.assertEqual(doc.items[0].rate, 3666.67)

    def test_keeps_rate_when_qp_unit_cost_is_empty(self):
        doc = FakeDoc(items=[FakeItem(rate=None, qp_unit_cost=None)])

        set_name(doc, None)

        self.assertIsNone(doc.items[0].rate)

    def test_does_nothing_for_existing_doc(self):
        doc = FakeDoc(
            is_new=False,
            order_confirmation_no="48967",
            items=[FakeItem(rate=None, qp_unit_cost=1000)],
        )

        set_name(doc, None)

        self.assertIsNone(doc.items[0].rate)
        self.assertFalse(doc.flags.name_set)


if __name__ == "__main__":
    unittest.main()
