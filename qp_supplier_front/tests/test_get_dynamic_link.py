# -*- coding: utf-8 -*-
"""
test_get_dynamic_link.py
========================
Pruebas unitarias para get_dynamic_link (services/get_data.py).
Verifica que se deduplican documentos cuando el child table Dynamic Link
tiene filas duplicadas para el mismo parent (evita filas repetidas en UI).
Aisladas de la base de datos y de Frappe usando mocks de sys.modules.

Ejecutar con: python3 -m unittest qp_supplier_front/tests/test_get_dynamic_link.py -v
"""
import sys
from unittest.mock import MagicMock

mock_frappe = MagicMock()
sys.modules['frappe'] = mock_frappe

import unittest

from qp_supplier_front.services.get_data import get_dynamic_link


class TestGetDynamicLink(unittest.TestCase):

    def setUp(self):
        mock_frappe.reset_mock()
        self.supplier = MagicMock()
        self.supplier.doctype = 'Supplier'
        self.supplier.name = 'SUP-0001'
        mock_frappe.get_doc.side_effect = lambda doctype, name: name

    def test_deduplicates_docs_by_name_preserving_order(self):
        mock_frappe.get_all.return_value = [
            {'name': 'Contact-0001', 'first_name': 'Ana'},
            {'name': 'Contact-0001', 'first_name': 'Ana'},
            {'name': 'Contact-0002', 'first_name': 'Luis'},
        ]

        result = get_dynamic_link(self.supplier, 'Contact')

        self.assertEqual(result, ['Contact-0001', 'Contact-0002'])
        self.assertEqual(mock_frappe.get_doc.call_count, 2)

    def test_returns_docs_in_creation_desc_order(self):
        mock_frappe.get_all.return_value = [
            {'name': 'Contact-0003', 'first_name': 'Nuevo'},
            {'name': 'Contact-0001', 'first_name': 'Viejo'},
        ]

        result = get_dynamic_link(self.supplier, 'Contact')

        self.assertEqual(result, ['Contact-0003', 'Contact-0001'])

    def test_no_duplicates_returns_all_docs(self):
        mock_frappe.get_all.return_value = [
            {'name': 'Contact-0001', 'first_name': 'Ana'},
            {'name': 'Contact-0002', 'first_name': 'Luis'},
        ]

        result = get_dynamic_link(self.supplier, 'Contact')

        self.assertEqual(result, ['Contact-0001', 'Contact-0002'])

    def test_empty_result_returns_empty_list(self):
        mock_frappe.get_all.return_value = []

        result = get_dynamic_link(self.supplier, 'Contact')

        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
