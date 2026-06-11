# -*- coding: utf-8 -*-
import unittest
import frappe
from qp_supplier_front.util.uppercase_utils import uppercase_form_inputs

class TestUppercaseMiddleware(unittest.TestCase):
    
    def setUp(self):
        self.original_form_dict = getattr(frappe.local, "form_dict", None)
        frappe.local.form_dict = frappe._dict()

    def tearDown(self):
        if self.original_form_dict is not None:
            frappe.local.form_dict = self.original_form_dict
        else:
            if hasattr(frappe.local, "form_dict"):
                delattr(frappe.local, "form_dict")

    def test_uppercase_form_inputs_matching_cmd(self):
        frappe.local.form_dict.update({
            "cmd": "qp_supplier_front.resources.information.basic.update",
            "supplier_name": "mi proveedor s.a.s",
            "tax_id": "900123456",
            "email_id": "test@example.com",
            "qp_is_foreigner_supplier": "true"
        })
        
        uppercase_form_inputs()
        
        self.assertEqual(frappe.local.form_dict["supplier_name"], "MI PROVEEDOR S.A.S")
        self.assertEqual(frappe.local.form_dict["tax_id"], "900123456")
        self.assertEqual(frappe.local.form_dict["email_id"], "test@example.com")
        self.assertEqual(frappe.local.form_dict["qp_is_foreigner_supplier"], "true")

    def test_uppercase_form_inputs_not_matching_cmd(self):
        frappe.local.form_dict.update({
            "cmd": "qp_supplier_front.resources.dispatch.purchase_order.create",
            "supplier_name": "mi proveedor s.a.s"
        })
        
        uppercase_form_inputs()
        
        self.assertEqual(frappe.local.form_dict["supplier_name"], "mi proveedor s.a.s")

    def test_sanitize_colombian_number(self):
        from qp_supplier_front.util.uppercase_utils import sanitize_colombian_number
        self.assertEqual(sanitize_colombian_number("1.250.000,00"), "1250000.00")
        self.assertEqual(sanitize_colombian_number("1250000,00"), "1250000.00")
        self.assertEqual(sanitize_colombian_number("0,05"), "0.05")
        self.assertEqual(sanitize_colombian_number("1250000.00"), "1250000.00")
        self.assertEqual(sanitize_colombian_number("1.250.000"), "1250000")
        self.assertEqual(sanitize_colombian_number(1250000.0), 1250000.0)
        self.assertEqual(sanitize_colombian_number(None), None)

    def test_uppercase_form_inputs_sanitizes_financial_fields(self):
        frappe.local.form_dict.update({
            "cmd": "qp_supplier_front.resources.information.financial.update",
            "qp_financial_assets": "1.250.000,00",
            "qp_financial_liabilities": "78.526.644,23",
            "supplier_name": "mi proveedor s.a.s"
        })
        
        uppercase_form_inputs()
        
        self.assertEqual(frappe.local.form_dict["qp_financial_assets"], "1250000.00")
        self.assertEqual(frappe.local.form_dict["qp_financial_liabilities"], "78526644.23")
        self.assertEqual(frappe.local.form_dict["supplier_name"], "MI PROVEEDOR S.A.S")


