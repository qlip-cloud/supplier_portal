# -*- coding: utf-8 -*-
"""
test_supplier_find.py
=====================
Pruebas unitarias para get_supplier_phone (services/get_data.py),
que respalda el autocompletado de tax_id con el teléfono sincronizado.
Aisladas de la base de datos y de Frappe usando mocks de sys.modules.

Ejecutar con: python3 -m unittest qp_supplier_front/tests/test_supplier_find.py -v
"""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

mock_frappe = MagicMock()
sys.modules['frappe'] = mock_frappe

import unittest

from qp_supplier_front.services import get_data
from qp_supplier_front.services.get_data import get_supplier_phone


class ContactStub(object):

    def __init__(self, mobile_no=None, is_primary_contact=0, phone_nos=None):
        self.mobile_no = mobile_no
        self.is_primary_contact = is_primary_contact
        self.phone_nos = phone_nos or []


class PartyStub(object):

    def __init__(self, phone_number=None):
        self.phone_number = phone_number


class TestGetSupplierPhone(unittest.TestCase):

    def setUp(self):
        mock_frappe.reset_mock()
        self.supplier = MagicMock()

    def test_prefers_party_phone_when_exists(self):
        with patch.object(get_data, 'get_party', return_value=PartyStub('6012345678')) as party_mock, \
                patch.object(get_data, 'get_dynamic_link') as contacts_mock:
            result = get_supplier_phone(self.supplier)
        self.assertEqual(result, '6012345678')
        party_mock.assert_called_once_with(self.supplier)
        contacts_mock.assert_not_called()

    def test_synced_supplier_phone_from_primary_contact_mobile_no(self):
        primary = ContactStub(mobile_no='31155512340000', is_primary_contact=1)
        with patch.object(get_data, 'get_party', return_value=None), \
                patch.object(get_data, 'get_dynamic_link', return_value=[primary]):
            result = get_supplier_phone(self.supplier)
        self.assertEqual(result, '31155512340000')

    def test_synced_supplier_falls_back_to_any_contact_mobile_no(self):
        contact = ContactStub(mobile_no='32055556780000', is_primary_contact=0)
        with patch.object(get_data, 'get_party', return_value=None), \
                patch.object(get_data, 'get_dynamic_link', return_value=[contact]):
            result = get_supplier_phone(self.supplier)
        self.assertEqual(result, '32055556780000')

    def test_prefers_primary_contact_over_others(self):
        primary = ContactStub(mobile_no='123', is_primary_contact=1)
        other = ContactStub(mobile_no='456', is_primary_contact=0)
        with patch.object(get_data, 'get_party', return_value=None), \
                patch.object(get_data, 'get_dynamic_link', return_value=[other, primary]):
            result = get_supplier_phone(self.supplier)
        self.assertEqual(result, '123')

    def test_uses_phone_nos_when_mobile_no_empty(self):
        contact = ContactStub(mobile_no=None, is_primary_contact=1, phone_nos=[SimpleNamespace(phone='999')])
        with patch.object(get_data, 'get_party', return_value=None), \
                patch.object(get_data, 'get_dynamic_link', return_value=[contact]):
            result = get_supplier_phone(self.supplier)
        self.assertEqual(result, '999')

    def test_no_phone_when_no_party_no_contacts(self):
        with patch.object(get_data, 'get_party', return_value=None), \
                patch.object(get_data, 'get_dynamic_link', return_value=[]):
            result = get_supplier_phone(self.supplier)
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
