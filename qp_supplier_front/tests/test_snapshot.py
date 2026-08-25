# -*- coding: utf-8 -*-
import unittest
import frappe
from qp_supplier_front.services.snapshot import _get_list_changes

class TestSnapshotLogic(unittest.TestCase):

    def test_get_list_changes_no_changes(self):
        old_list = [
            {"name": "ADDR-0001", "address_line1": "Calle 1", "city": "Bogota"},
            {"name": "ADDR-0002", "address_line1": "Calle 2", "city": "Medellin"}
        ]
        new_list = [
            {"name": "ADDR-0001", "address_line1": "Calle 1", "city": "Bogota"},
            {"name": "ADDR-0002", "address_line1": "Calle 2", "city": "Medellin"}
        ]
        result = _get_list_changes(old_list, new_list, ["address_line1", "city"])
        self.assertEqual(result, [])

    def test_get_list_changes_with_modified_fields(self):
        old_list = [
            {"name": "ADDR-0001", "address_line1": "Calle 1", "city": "Bogota"}
        ]
        new_list = [
            {"name": "ADDR-0001", "address_line1": "Calle 1 Modificada", "city": "Bogota"}
        ]
        result = _get_list_changes(old_list, new_list, ["address_line1", "city"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "ADDR-0001")
        self.assertEqual(result[0]["type"], "modified")
        self.assertIn("address_line1", result[0]["changes"])
        self.assertEqual(result[0]["changes"]["address_line1"], "Calle 1")

    def test_get_list_changes_with_added_item(self):
        old_list = [
            {"name": "ADDR-0001", "address_line1": "Calle 1", "city": "Bogota"}
        ]
        new_list = [
            {"name": "ADDR-0001", "address_line1": "Calle 1", "city": "Bogota"},
            {"name": "ADDR-0002", "address_line1": "Calle 2", "city": "Medellin"}
        ]
        result = _get_list_changes(old_list, new_list, ["address_line1", "city"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "ADDR-0002")
        self.assertEqual(result[0]["type"], "added")

    def test_get_list_changes_with_removed_item(self):
        old_list = [
            {"name": "ADDR-0001", "address_line1": "Calle 1", "city": "Bogota"},
            {"name": "ADDR-0002", "address_line1": "Calle 2", "city": "Medellin"}
        ]
        new_list = [
            {"name": "ADDR-0001", "address_line1": "Calle 1", "city": "Bogota"}
        ]
        result = _get_list_changes(old_list, new_list, ["address_line1", "city"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "ADDR-0002")
        self.assertEqual(result[0]["type"], "removed")

    def test_get_list_changes_positional_fallback(self):
        old_list = [
            {"address_line1": "Calle 1", "city": "Bogota"},
            {"address_line1": "Calle 2", "city": "Medellin"}
        ]
        new_list = [
            {"address_line1": "Calle 1 Modificada", "city": "Bogota"},
            {"address_line1": "Calle 2", "city": "Medellin"}
        ]
        result = _get_list_changes(old_list, new_list, ["address_line1", "city"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "modified")
        self.assertIn("address_line1", result[0]["changes"])
        self.assertEqual(result[0]["changes"]["address_line1"], "Calle 1")

    def test_compare_snapshot_logic(self):
        from qp_supplier_front.services.snapshot import compare_snapshot_with_current

        original_get_all = frappe.get_all
        original_parse_json = frappe.parse_json

        try:
            snapshot_mock_data = {
                "supplier": {
                    "supplier_name": "Proveedor Original",
                    "qp_legal_name": "Representante Original"
                },
                "party": {
                    "phone_number": "1234567"
                },
                "addresses": [],
                "contacts": [],
                "bank_accounts": [],
                "shareholders": [],
                "documents": {}
            }

            frappe.get_all = lambda *args, **kwargs: [frappe._dict(snapshot_data=frappe.as_json(snapshot_mock_data))]

            import qp_supplier_front.services.snapshot as snap_module
            original_get_dict = snap_module.get_supplier_data_dict

            current_mock_data = {
                "supplier": {
                    "supplier_name": "Proveedor Modificado",
                    "qp_legal_name": "Representante Original"
                },
                "party": {
                    "phone_number": "7654321"
                },
                "addresses": [],
                "contacts": [],
                "bank_accounts": [],
                "shareholders": [],
                "documents": {}
            }
            snap_module.get_supplier_data_dict = lambda supplier_id: current_mock_data

            fields, tabs, items = compare_snapshot_with_current("dummy_id")

            self.assertIn("supplier_name", fields)
            self.assertEqual(fields["supplier_name"], "Proveedor Original")
            self.assertNotIn("qp_legal_name", fields)

            self.assertIn("phone_number", fields)
            self.assertEqual(fields["phone_number"], "1234567")

            self.assertEqual(items, {})

            # Verificar que los tabs se marcan según FIELD_TO_TAB
            self.assertIn("basic", tabs)
            # supplier_name y phone_number están en basic, qp_legal_name no cambió

            snap_module.get_supplier_data_dict = original_get_dict

        finally:
            frappe.get_all = original_get_all
            frappe.parse_json = original_parse_json

    def test_compare_snapshot_with_list_changes(self):
        from qp_supplier_front.services.snapshot import compare_snapshot_with_current

        original_get_all = frappe.get_all
        original_parse_json = frappe.parse_json

        try:
            snapshot_mock_data = {
                "supplier": {},
                "party": {},
                "documents": {},
                "addresses": [
                    {"name": "ADDR-0001", "address_line1": "Calle Original", "city": "Bogota"}
                ],
                "contacts": [],
                "bank_accounts": [],
                "shareholders": []
            }

            frappe.get_all = lambda *args, **kwargs: [frappe._dict(snapshot_data=frappe.as_json(snapshot_mock_data))]

            import qp_supplier_front.services.snapshot as snap_module
            original_get_dict = snap_module.get_supplier_data_dict

            current_mock_data = {
                "supplier": {},
                "party": {},
                "documents": {},
                "addresses": [
                    {"name": "ADDR-0001", "address_line1": "Calle Modificada", "city": "Bogota"}
                ],
                "contacts": [],
                "bank_accounts": [],
                "shareholders": []
            }
            snap_module.get_supplier_data_dict = lambda supplier_id: current_mock_data

            fields, tabs, items = compare_snapshot_with_current("dummy_id")

            self.assertEqual(fields, {})
            self.assertIn("address", tabs)
            self.assertIn("address", items)
            self.assertEqual(len(items["address"]), 1)
            self.assertEqual(items["address"][0]["name"], "ADDR-0001")
            self.assertEqual(items["address"][0]["type"], "modified")
            self.assertIn("address_line1", items["address"][0]["changes"])
            self.assertEqual(items["address"][0]["changes"]["address_line1"], "Calle Original")

            snap_module.get_supplier_data_dict = original_get_dict

        finally:
            frappe.get_all = original_get_all
            frappe.parse_json = original_parse_json
