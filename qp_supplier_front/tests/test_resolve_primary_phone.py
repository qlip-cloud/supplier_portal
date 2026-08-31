# -*- coding: utf-8 -*-
"""
test_resolve_primary_phone.py
==============================
Prueba unitaria de `resolve_primary_phone` (www/information/index.py).
Verifica que el telefono a mostrar se calcula sin modificar en DB el
contacto primario (no se promueve ni se persiste ningun cambio).

Ejecutar con: python3 -m unittest qp_supplier_front/tests/test_resolve_primary_phone.py -v
"""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

mock_frappe = MagicMock()
sys.modules['frappe'] = mock_frappe

import unittest

from qp_supplier_front.www.information.index import resolve_primary_phone


def _make_contact(is_primary_contact=0, mobile_no=None, phone_nos=None):
    return SimpleNamespace(
        is_primary_contact=is_primary_contact,
        mobile_no=mobile_no,
        phone_nos=phone_nos or [],
    )


class TestResolvePrimaryPhone(unittest.TestCase):

    def test_returns_primary_contact_phone(self):
        contacts = [
            _make_contact(is_primary_contact=1, mobile_no="300111"),
            _make_contact(mobile_no="300222"),
        ]

        self.assertEqual(resolve_primary_phone(contacts), "300111")

    def test_falls_back_to_any_contact_with_phone(self):
        contacts = [
            _make_contact(is_primary_contact=1),
            _make_contact(mobile_no="300222"),
        ]

        self.assertEqual(resolve_primary_phone(contacts), "300222")

    def test_uses_phone_nos_when_no_mobile(self):
        contacts = [
            _make_contact(is_primary_contact=1, phone_nos=[SimpleNamespace(phone="300333")]),
        ]

        self.assertEqual(resolve_primary_phone(contacts), "300333")

    def test_returns_none_without_phones(self):
        contacts = [
            _make_contact(is_primary_contact=1),
            _make_contact(),
        ]

        self.assertIsNone(resolve_primary_phone(contacts))

    def test_returns_none_without_contacts(self):
        self.assertIsNone(resolve_primary_phone([]))
        self.assertIsNone(resolve_primary_phone(None))


if __name__ == "__main__":
    unittest.main()