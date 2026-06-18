# -*- coding: utf-8 -*-
import unittest
import frappe
from qp_supplier_front.services.snapshot import _has_list_changes

class TestSnapshotLogic(unittest.TestCase):

    def test_has_list_changes_no_changes(self):
        old_list = [
            {"name": "ADDR-0001", "address_line1": "Calle 1", "city": "Bogota"},
            {"name": "ADDR-0002", "address_line1": "Calle 2", "city": "Medellin"}
        ]
        new_list = [
            {"name": "ADDR-0001", "address_line1": "Calle 1", "city": "Bogota"},
            {"name": "ADDR-0002", "address_line1": "Calle 2", "city": "Medellin"}
        ]
        self.assertFalse(_has_list_changes(old_list, new_list, ["address_line1", "city"]))

    def test_has_list_changes_with_modified_fields(self):
        old_list = [
            {"name": "ADDR-0001", "address_line1": "Calle 1", "city": "Bogota"}
        ]
        new_list = [
            {"name": "ADDR-0001", "address_line1": "Calle 1 Modificada", "city": "Bogota"}
        ]
        self.assertTrue(_has_list_changes(old_list, new_list, ["address_line1", "city"]))

    def test_has_list_changes_with_added_item(self):
        old_list = [
            {"name": "ADDR-0001", "address_line1": "Calle 1", "city": "Bogota"}
        ]
        new_list = [
            {"name": "ADDR-0001", "address_line1": "Calle 1", "city": "Bogota"},
            {"name": "ADDR-0002", "address_line1": "Calle 2", "city": "Medellin"}
        ]
        self.assertTrue(_has_list_changes(old_list, new_list, ["address_line1", "city"]))

    def test_has_list_changes_with_removed_item(self):
        old_list = [
            {"name": "ADDR-0001", "address_line1": "Calle 1", "city": "Bogota"},
            {"name": "ADDR-0002", "address_line1": "Calle 2", "city": "Medellin"}
        ]
        new_list = [
            {"name": "ADDR-0001", "address_line1": "Calle 1", "city": "Bogota"}
        ]
        self.assertTrue(_has_list_changes(old_list, new_list, ["address_line1", "city"]))

    def test_compare_snapshot_logic(self):
        # Mock de get_supplier_data_dict y compare_snapshot_with_current
        from qp_supplier_front.services.snapshot import compare_snapshot_with_current
        
        # Vamos a mockear la base de datos de frappe temporalmente para esta prueba
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
            
            # Mock de base de datos
            frappe.get_all = lambda *args, **kwargs: [frappe._dict(snapshot_data=frappe.as_json(snapshot_mock_data))]
            
            # Mock de get_supplier_data_dict
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
            
            fields, tabs = compare_snapshot_with_current("dummy_id")
            
            # Verificar que detectó las modificaciones
            self.assertIn("supplier_name", fields)
            self.assertEqual(fields["supplier_name"], "Proveedor Original")
            self.assertNotIn("qp_legal_name", fields)
            
            self.assertIn("phone_number", fields)
            self.assertEqual(fields["phone_number"], "1234567")
            
            # Restaurar mock
            snap_module.get_supplier_data_dict = original_get_dict
            
        finally:
            frappe.get_all = original_get_all
            frappe.parse_json = original_parse_json
