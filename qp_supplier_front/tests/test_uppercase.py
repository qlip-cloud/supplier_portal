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
