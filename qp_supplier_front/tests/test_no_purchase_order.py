# -*- coding: utf-8 -*-
"""
test_no_purchase_order.py
=========================
Pruebas del nucleo puro de la politica "credito sin OC".

Nucleo puro: no requiere Frappe ni base de datos.
Ejecutar con: python -m unittest qp_supplier_front.tests.test_no_purchase_order
"""
import unittest

from qp_supplier_front.uses_cases.documenteme.no_purchase_order import (
    DEFAULT_ASSIGN_WHEN_NO_ACTION,
    INVOICE_TYPE_CASH,
    INVOICE_TYPE_CREDIT,
    NO_ACTION,
    has_purchase_orders,
    invoice_type_of,
    is_pending_purchase_order,
    is_without_po_credit,
    should_assign_without_po,
    should_skip_reject_without_po,
)


def _credit(without_po=True, **extra):
    doc = {"nvfac_conv": "2", "nvfac_orde": "" if without_po else "OC-1"}
    doc.update(extra)
    return doc


def _cash(without_po=True, **extra):
    doc = {"nvfac_conv": "1", "nvfac_orde": "" if without_po else "OC-1"}
    doc.update(extra)
    return doc


class TestHasPurchaseOrders(unittest.TestCase):

    def test_empty(self):
        self.assertFalse(has_purchase_orders({}))

    def test_single(self):
        self.assertTrue(has_purchase_orders({"nvfac_orde": "OC-1"}))

    def test_multiple_with_spaces(self):
        self.assertTrue(has_purchase_orders({"nvfac_orde": " OC-1, , OC-2 "}))

    def test_whitespace_only(self):
        self.assertFalse(has_purchase_orders({"nvfac_orde": "   "}))


class TestInvoiceType(unittest.TestCase):

    def test_credit(self):
        self.assertEqual(invoice_type_of(_credit()), INVOICE_TYPE_CREDIT)

    def test_empty_conversion_is_credit(self):
        self.assertEqual(
            invoice_type_of({"nvfac_conv": ""}), INVOICE_TYPE_CREDIT)

    def test_cash(self):
        self.assertEqual(invoice_type_of(_cash()), INVOICE_TYPE_CASH)


class TestIsWithoutPoCredit(unittest.TestCase):

    def test_credit_without_po(self):
        self.assertTrue(is_without_po_credit(_credit()))

    def test_credit_with_po(self):
        self.assertFalse(is_without_po_credit(_credit(without_po=False)))

    def test_cash_without_po_is_not_scope(self):
        self.assertFalse(is_without_po_credit(_cash()))

    def test_credit_note_is_not_scope(self):
        self.assertFalse(is_without_po_credit(_credit(nvtip_docu="C")))

    def test_delivery_is_not_scope(self):
        doc = _credit()
        self.assertFalse(
            is_without_po_credit(doc, is_delivery_fn=lambda d: True))

    def test_delivery_code_in_oc_is_not_without_po(self):
        self.assertFalse(
            is_without_po_credit(_credit(without_po=False)))


class TestPendingPurchaseOrder(unittest.TestCase):

    def test_flag_off(self):
        self.assertFalse(is_pending_purchase_order(_credit(), enabled=False))

    def test_flag_on_credit_without_po(self):
        self.assertTrue(is_pending_purchase_order(_credit(), enabled=True))

    def test_flag_on_cash_without_po(self):
        self.assertFalse(is_pending_purchase_order(_cash(), enabled=True))

    def test_flag_on_credit_with_po(self):
        self.assertFalse(
            is_pending_purchase_order(
                _credit(without_po=False), enabled=True))

    def test_flag_on_credit_note(self):
        self.assertFalse(
            is_pending_purchase_order(
                _credit(nvtip_docu="C"), enabled=True))

    def test_flag_on_delivery(self):
        self.assertFalse(
            is_pending_purchase_order(
                _credit(), enabled=True, is_delivery_fn=lambda d: True))

    def test_default_knob_assigns_with_no_action(self):
        self.assertTrue(DEFAULT_ASSIGN_WHEN_NO_ACTION)
        self.assertTrue(
            is_pending_purchase_order(
                _credit(), enabled=True, supplier_rule={"rule_code": NO_ACTION}))

    def test_knob_false_no_action_does_not_assign(self):
        self.assertFalse(
            is_pending_purchase_order(
                _credit(), enabled=True, assign_when_no_action=False,
                supplier_rule={"rule_code": NO_ACTION}))

    def test_knob_false_other_rule_still_assigns(self):
        self.assertTrue(
            is_pending_purchase_order(
                _credit(), enabled=True, assign_when_no_action=False,
                supplier_rule={"rule_code": "no_po"}))


class TestShouldAssignWithoutPo(unittest.TestCase):

    def test_assigns(self):
        self.assertTrue(should_assign_without_po(_credit(), enabled=True))

    def test_already_assigned(self):
        self.assertFalse(
            should_assign_without_po(
                _credit(), enabled=True, already_assigned=True))

    def test_not_in_queue(self):
        self.assertFalse(
            should_assign_without_po(_credit(), enabled=True, in_queue=False))

    def test_flag_off(self):
        self.assertFalse(should_assign_without_po(_credit(), enabled=False))


class TestShouldSkipRejectWithoutPo(unittest.TestCase):

    def test_skips_credit_without_po_with_flag(self):
        self.assertTrue(
            should_skip_reject_without_po(_credit(), enabled=True))

    def test_does_not_skip_with_flag_off(self):
        self.assertFalse(
            should_skip_reject_without_po(_credit(), enabled=False))

    def test_does_not_skip_cash(self):
        self.assertFalse(
            should_skip_reject_without_po(_cash(), enabled=True))

    def test_does_not_skip_with_po(self):
        self.assertFalse(
            should_skip_reject_without_po(
                _credit(without_po=False), enabled=True))


if __name__ == "__main__":
    unittest.main()
