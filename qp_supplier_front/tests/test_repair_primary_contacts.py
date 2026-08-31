# -*- coding: utf-8 -*-
"""
test_repair_primary_contacts.py
================================
Pruebas unitarias para la reparacion de contactos primarios
(services/repair_primary_contacts.py).
Aisladas de la base de datos y de Frappe usando mocks de sys.modules.

Ejecutar con: python3 -m unittest qp_supplier_front/tests/test_repair_primary_contacts.py -v
"""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

mock_frappe = MagicMock()
sys.modules['frappe'] = mock_frappe

import unittest

from qp_supplier_front.services import repair_primary_contacts
from qp_supplier_front.services.repair_primary_contacts import (
    _pick_restore_candidate,
    _pick_designate_candidate,
    run,
)


def _make_contact(name, user="", mobile_no="", is_primary_contact=0, creation="2026-01-01 00:00:00"):
    return SimpleNamespace(
        name=name,
        user=user,
        mobile_no=mobile_no,
        is_primary_contact=is_primary_contact,
        creation=creation,
        email_ids=[SimpleNamespace(email_id=user or "a@example.com")] if not user else [],
    )


def _make_supplier(name, owner="Administrator"):
    return SimpleNamespace(name=name, owner=owner, doctype="Supplier")


class TestPickCandidates(unittest.TestCase):

    def test_pick_restore_prefers_owner_match(self):
        owner_contact = _make_contact("C-OWNER", user="owner@example.com", creation="2026-02-01")
        older_contact = _make_contact("C-OLDER", user="other@example.com", creation="2026-01-01")
        contacts = [older_contact, owner_contact]

        result = _pick_restore_candidate(contacts, "owner@example.com")

        self.assertIs(result, owner_contact)

    def test_pick_restore_earliest_when_no_owner(self):
        older_contact = _make_contact("C-OLDER", user="a@example.com", creation="2026-01-01")
        newer_contact = _make_contact("C-NEWER", user="b@example.com", creation="2026-02-01")
        contacts = [newer_contact, older_contact]

        result = _pick_restore_candidate(contacts, "nobody@example.com")

        self.assertIs(result, older_contact)

    def test_pick_restore_none_without_user(self):
        contacts = [_make_contact("C-1"), _make_contact("C-2")]

        result = _pick_restore_candidate(contacts, "x@example.com")

        self.assertIsNone(result)

    def test_pick_designate_prefers_user_and_earliest(self):
        user_contact = _make_contact("C-USER", user="m@example.com", creation="2026-02-01")
        older_user = _make_contact("C-OLD-USER", user="n@example.com", creation="2026-01-01")
        contacts = [_make_contact("C-NOUSER", creation="2025-01-01"), user_contact, older_user]

        result = _pick_designate_candidate(contacts)

        self.assertIs(result, older_user)

    def test_pick_designate_earliest_without_user(self):
        oldest = _make_contact("C-OLDEST", creation="2025-01-01")
        newer = _make_contact("C-NEWER", creation="2026-01-01")

        result = _pick_designate_candidate([newer, oldest])

        self.assertIs(result, oldest)


class TestRun(unittest.TestCase):

    def setUp(self):
        self.get_dynamic_link_patcher = patch.object(
            repair_primary_contacts, "get_dynamic_link"
        )
        self.mock_get_dynamic_link = self.get_dynamic_link_patcher.start()
        mock_frappe.reset_mock()
        mock_frappe.get_all.return_value = ["SUP-1"]
        mock_frappe.get_doc.side_effect = lambda doctype, name: _make_supplier(name)

    def tearDown(self):
        self.get_dynamic_link_patcher.stop()

    def test_dry_run_restores_primary_with_user(self):
        primary_sin_user = _make_contact("C-PRIMARY", mobile_no="300", is_primary_contact=1, creation="2026-02-01")
        creador = _make_contact("C-CREATOR", user="creador@example.com", mobile_no="311", creation="2026-01-01")
        self.mock_get_dynamic_link.return_value = [primary_sin_user, creador]

        report = run(dry_run=True)

        self.assertEqual(report[0]["action"], "restaurar_primario")
        self.assertFalse(mock_frappe.db.set_value.called)
        self.assertFalse(mock_frappe.db.commit.called)

    def test_apply_restores_primary_and_unsets_previous(self):
        primary_sin_user = _make_contact("C-PRIMARY", mobile_no="300", is_primary_contact=1, creation="2026-02-01")
        creador = _make_contact("C-CREATOR", user="creador@example.com", mobile_no="311", creation="2026-01-01")
        self.mock_get_dynamic_link.return_value = [primary_sin_user, creador]

        report = run(dry_run=False)

        self.assertEqual(report[0]["action"], "restaurar_primario")
        calls = [c[0] for c in mock_frappe.db.set_value.call_args_list]
        self.assertIn(("Contact", "C-PRIMARY", "is_primary_contact", 0), calls)
        self.assertIn(("Contact", "C-CREATOR", "is_primary_contact", 1), calls)
        self.assertTrue(mock_frappe.db.commit.called)

    def test_dry_run_designates_sync_primary(self):
        synced = _make_contact("0-1001", user="mail@example.com", mobile_no="300", creation="2026-01-01")
        otro = _make_contact("1-1001", user="mail2@example.com", mobile_no="301", creation="2026-02-01")
        self.mock_get_dynamic_link.return_value = [otro, synced]

        report = run(dry_run=True)

        self.assertEqual(report[0]["action"], "designar_primario_sync")
        self.assertFalse(mock_frappe.db.set_value.called)

    def test_apply_designates_sync_primary(self):
        synced = _make_contact("0-1001", user="mail@example.com", mobile_no="300", creation="2026-01-01")
        self.mock_get_dynamic_link.return_value = [synced]

        report = run(dry_run=False)

        self.assertEqual(report[0]["action"], "designar_primario_sync")
        calls = [c[0] for c in mock_frappe.db.set_value.call_args_list]
        self.assertIn(("Contact", "0-1001", "is_primary_contact", 1), calls)

    def test_ok_when_primary_has_user(self):
        primario = _make_contact("C-PRIMARY", user="usu@example.com", mobile_no="300", is_primary_contact=1)
        self.mock_get_dynamic_link.return_value = [primario, _make_contact("C-X", user="x@example.com")]

        report = run(dry_run=False)

        self.assertEqual(report[0]["action"], "ok")
        self.assertFalse(mock_frappe.db.set_value.called)

    def test_restores_and_copies_phone_until_primary_has_one(self):
        primary_sin_user = _make_contact("C-PRIMARY", mobile_no="300", is_primary_contact=1)
        creador = _make_contact("C-CREATOR", user="creador@example.com", mobile_no="", creation="2026-01-01")
        self.mock_get_dynamic_link.return_value = [primary_sin_user, creador]

        run(dry_run=False)

        calls = [c[0] for c in mock_frappe.db.set_value.call_args_list]
        self.assertIn(("Contact", "C-CREATOR", "mobile_no", "300"), calls)

    def test_single_contact_without_primary_is_designated(self):
        unico = _make_contact("0-1001", user="mail@example.com", mobile_no="300", creation="2026-01-01")
        self.mock_get_dynamic_link.return_value = [unico]

        report = run(dry_run=False)

        self.assertEqual(report[0]["action"], "designar_primario_sync")


if __name__ == "__main__":
    unittest.main()