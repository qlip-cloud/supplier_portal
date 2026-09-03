# -*- coding: utf-8 -*-
"""
test_supplier_approve.py
========================
Pruebas unitarias para el fallback de contacto del payload GP
(infrastructure/strategies/gp/supplier_strategy.py).
Cubren get_contact y get_contact_mail: el fallback a email_ids cuando el contacto
no tiene user (caso que rompia con AttributeError: 'str' object has no attribute 'user').
Aisladas de la base de datos y de Frappe usando mocks de sys.modules.

Ejecutar con: python3 -m unittest qp_supplier_front/tests/test_supplier_approve.py -v
"""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

mock_frappe = MagicMock()
sys.modules['frappe'] = mock_frappe

sys.modules['qp_authorization'] = MagicMock()
sys.modules['qp_authorization.use_case'] = MagicMock()
sys.modules['qp_authorization.use_case.bearer'] = MagicMock()
sys.modules['qp_authorization.use_case.bearer.authorize'] = MagicMock()
sys.modules['qp_supplier_front.www'] = MagicMock()
sys.modules['qp_supplier_front.www.information'] = MagicMock()
sys.modules['qp_supplier_front.www.information.index'] = MagicMock()

import unittest

from qp_supplier_front.infrastructure.strategies.gp.supplier_strategy import (
    get_contact,
    get_contact_mail,
)


def _make_contact(is_primary_contact=None, user="", email_ids=None):
    return SimpleNamespace(
        is_primary_contact=is_primary_contact or 0,
        user=user,
        email_ids=email_ids or [],
    )


def _make_supplier(contact):
    return SimpleNamespace(contacts=[contact])


class TestGetContact(unittest.TestCase):

    def setUp(self):
        self.mock_get_dynamic_link = MagicMock()
        import qp_supplier_front.infrastructure.strategies.gp.supplier_strategy as strategy
        self._original = strategy.get_dynamic_link
        strategy.get_dynamic_link = self.mock_get_dynamic_link

    def tearDown(self):
        import qp_supplier_front.infrastructure.strategies.gp.supplier_strategy as strategy
        strategy.get_dynamic_link = self._original

    def test_primary_contact_without_user_is_returned(self):
        contact = _make_contact(is_primary_contact=1, email_ids=[SimpleNamespace(email_id="a@example.com")])
        self.mock_get_dynamic_link.return_value = [contact]

        result = get_contact(_make_supplier(contact))

        self.assertIs(result, contact)

    def test_non_primary_contact_with_user_is_returned(self):
        contact = _make_contact(is_primary_contact=0, user="b@example.com")
        self.mock_get_dynamic_link.return_value = [contact]

        result = get_contact(_make_supplier(contact))

        self.assertIs(result, contact)

    def test_no_contacts_returns_none(self):
        self.mock_get_dynamic_link.return_value = []

        result = get_contact(_make_supplier(None))

        self.assertIsNone(result)

    def test_primary_with_user_has_priority(self):
        primary = _make_contact(is_primary_contact=1, user="primary@example.com")
        other = _make_contact(is_primary_contact=0, user="other@example.com")
        self.mock_get_dynamic_link.return_value = [other, primary]

        result = get_contact(_make_supplier(primary))

        self.assertIs(result, primary)


class TestGetContactMail(unittest.TestCase):

    def test_returns_user_when_present(self):
        contact = _make_contact(user="user@example.com", email_ids=[SimpleNamespace(email_id="mail@example.com")])

        self.assertEqual(get_contact_mail(contact), "user@example.com")

    def test_returns_email_when_user_empty(self):
        contact = _make_contact(email_ids=[SimpleNamespace(email_id="mail@example.com")])

        self.assertEqual(get_contact_mail(contact), "mail@example.com")

    def test_returns_blank_when_no_email(self):
        contact = _make_contact()

        self.assertEqual(get_contact_mail(contact), "")

    def test_returns_blank_when_contact_none(self):
        self.assertEqual(get_contact_mail(None), "")