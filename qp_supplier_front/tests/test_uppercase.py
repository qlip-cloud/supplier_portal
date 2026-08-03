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

    def test_sanitize_colombian_number_reported_cases(self):
        from qp_supplier_front.util.uppercase_utils import sanitize_colombian_number
        self.assertEqual(sanitize_colombian_number("8.651,22"), "8651.22")
        self.assertEqual(sanitize_colombian_number("9.875,46"), "9875.46")

    def test_financial_update_sanitizes_masked_values(self):
        from qp_supplier_front.resources.information import financial

        captured = {}
        original_handler = financial.update_financial
        original_response = financial.response

        def fake_handler(supplier_id, qp_financial_assets, qp_financial_liabilities, qp_financial_equity,
                         qp_financial_details_income, qp_financial_monthly_income,
                         qp_financial_monthly_expenses, qp_financial_other_income):
            captured.update({
                "supplier_id": supplier_id,
                "qp_financial_assets": qp_financial_assets,
                "qp_financial_liabilities": qp_financial_liabilities,
                "qp_financial_equity": qp_financial_equity,
                "qp_financial_details_income": qp_financial_details_income,
                "qp_financial_monthly_income": qp_financial_monthly_income,
                "qp_financial_monthly_expenses": qp_financial_monthly_expenses,
                "qp_financial_other_income": qp_financial_other_income
            })
            return {"supplier": {}}

        def fake_response(status, msg, data=None):
            captured["status"] = status

        financial.update_financial = fake_handler
        financial.response = fake_response

        try:
            financial.update(
                supplier_id="SUP-0001",
                qp_financial_assets="8.651,22",
                qp_financial_liabilities="9.875,46",
                qp_financial_equity="1.250.000,00",
                qp_financial_other_income="0,05",
                qp_financial_monthly_income="250000",
                qp_financial_monthly_expenses="1250000.00",
                qp_financial_details_income="Venta de activos"
            )
        finally:
            financial.update_financial = original_handler
            financial.response = original_response

        self.assertEqual(captured["status"], 200)
        self.assertEqual(captured["supplier_id"], "SUP-0001")
        self.assertEqual(captured["qp_financial_assets"], "8651.22")
        self.assertEqual(captured["qp_financial_liabilities"], "9875.46")
        self.assertEqual(captured["qp_financial_equity"], "1250000.00")
        self.assertEqual(captured["qp_financial_other_income"], "0.05")
        self.assertEqual(captured["qp_financial_monthly_income"], "250000")
        self.assertEqual(captured["qp_financial_monthly_expenses"], "1250000.00")
        self.assertEqual(captured["qp_financial_details_income"], "Venta de activos")

    def test_international_update_sanitizes_amount(self):
        from qp_supplier_front.resources.information import international

        captured = {}
        original_handler = international.update_international
        original_response = international.response

        def fake_handler(supplier_id, qp_financial_currency_foreigner, qp_financial_which_currency_foreigner,
                         qp_financial_other_operations, qp_financial_item_foreigner,
                         qp_financial_account_currency_foreigner, qp_financial_item_type,
                         qp_financial_item_number, qp_financial_entity, qp_financial_amount,
                         qp_financial_city, qp_financial_country, qp_financial_currency):
            captured["qp_financial_amount"] = qp_financial_amount
            captured["qp_financial_entity"] = qp_financial_entity
            return {"supplier": {}}

        def fake_response(status, msg, data=None):
            captured["status"] = status

        international.update_international = fake_handler
        international.response = fake_response

        try:
            international.update(
                supplier_id="SUP-0001",
                qp_financial_currency_foreigner="SI",
                qp_financial_which_currency_foreigner="DOLAR",
                qp_financial_other_operations="NO",
                qp_financial_item_foreigner="1",
                qp_financial_account_currency_foreigner="USD",
                qp_financial_item_type="ACTIVO",
                qp_financial_item_number="2",
                qp_financial_entity="Banco X",
                qp_financial_amount="8.651,22",
                qp_financial_city="Bogota",
                qp_financial_country="Colombia",
                qp_financial_currency="USD"
            )
        finally:
            international.update_international = original_handler
            international.response = original_response

        self.assertEqual(captured["status"], 200)
        self.assertEqual(captured["qp_financial_amount"], "8651.22")
        self.assertEqual(captured["qp_financial_entity"], "Banco X")


