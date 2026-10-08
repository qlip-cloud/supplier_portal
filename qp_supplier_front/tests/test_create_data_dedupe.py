# -*- coding: utf-8 -*-
"""
test_create_data_dedupe.py
==========================
Pruebas unitarias para la deduplicacion del primer contacto (Option A):

- create_first_contact reutiliza el contacto del proveedor (sync) cuando el
  correo coincide, en lugar de crear uno nuevo.
- set_contact no duplica filas de email_ids / phone_nos al reutilizar.
- _remove_orphan_contact_duplicates borra solo los contactos huerfanos
  (sin links) creados por el job por defecto de Frappe.

Aisladas de la base de datos usando mocks de sys.modules.

Ejecutar con: python3 -m unittest qp_supplier_front/tests/test_create_data_dedupe.py -v
"""
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

mock_frappe = MagicMock()
sys.modules['frappe'] = mock_frappe

import unittest

from qp_supplier_front.services import create_data


class LinkStub(object):

    def __init__(self, link_doctype, link_name):
        self.link_doctype = link_doctype
        self.link_name = link_name

    def get(self, key, default=None):
        return getattr(self, key, default)


class EmailStub(object):

    def __init__(self, email_id):
        self.email_id = email_id

    def get(self, key, default=None):
        return getattr(self, key, default)


class PhoneStub(object):

    def __init__(self, phone):
        self.phone = phone

    def get(self, key, default=None):
        return getattr(self, key, default)


class ContactStub(object):

    def __init__(self, name, email_ids=None, phone_nos=None, links=None,
                 user=None, email_id=""):
        self.name = name
        self.email_id = email_id
        self.user = user
        self.email_ids = list(email_ids or [])
        self.phone_nos = list(phone_nos or [])
        self.links = list(links or [])
        self.first_name = None
        self.qp_contact_type = None
        self.is_primary_contact = 0
        self.mobile_no = None
        self.saved = 0
        self.inserted = 0

    def get(self, key, default=None):
        return getattr(self, key, default)

    def append(self, fieldname, row):
        getattr(self, fieldname).append(row)

    def save(self):
        self.saved += 1

    def insert(self):
        self.inserted += 1


class TestSetContact(unittest.TestCase):

    def setUp(self):
        mock_frappe.reset_mock()
        self.supplier = SimpleNamespace(doctype="Supplier", name="805026744", supplier_name="BANDAS CORREAS INDUSTRIALES SAS")

    def test_no_duplicate_email_or_phone_on_reuse(self):
        contact = ContactStub(
            "c1",
            email_ids=[EmailStub("user@yopmail.com")],
            phone_nos=[PhoneStub("57 3188863119")],
        )
        with patch.object(create_data, 'get_dynamic_link', return_value=[]):
            create_data.set_contact(
                "Contact", contact, self.supplier,
                "user@yopmail.com", "57 3188863119"
            )

        self.assertEqual(len(contact.email_ids), 1)
        self.assertEqual(len(contact.phone_nos), 1)
        self.assertEqual(len(contact.links), 1)
        self.assertEqual(contact.is_primary_contact, 1)

    def test_appends_email_when_missing(self):
        contact = ContactStub("c1")
        with patch.object(create_data, 'get_dynamic_link', return_value=[]):
            create_data.set_contact("Contact", contact, self.supplier, "user@yopmail.com")

        self.assertEqual(len(contact.email_ids), 1)


class TestFindFirstContact(unittest.TestCase):

    def setUp(self):
        mock_frappe.reset_mock()
        self.supplier = SimpleNamespace(doctype="Supplier", name="805026744", supplier_name="BANDAS CORREAS INDUSTRIALES SAS")
        self.supplier_contact = ContactStub(
            "2545-805029159",
            email_ids=[EmailStub("user@yopmail.com")],
            links=[LinkStub("Supplier", "805026744")],
        )

    def test_prefers_supplier_contact_by_email(self):
        with patch.object(
            create_data, 'get_dynamic_link',
            return_value=[self.supplier_contact]
        ):
            result = create_data._find_first_contact(
                self.supplier, "user@yopmail.com", "user@yopmail.com"
            )

        self.assertEqual(result, self.supplier_contact)

    def test_falls_back_to_user_contact(self):
        other = ContactStub("2545-805029159", email_ids=[EmailStub("otro@yopmail.com")])
        user_contact = ContactStub("user-contact", user="user@yopmail.com")
        with patch.object(create_data, 'get_dynamic_link', return_value=[other]), \
                patch.object(
                    create_data.frappe, 'get_value',
                    return_value="user-contact"
                ), \
                patch.object(
                    create_data.frappe, 'get_doc',
                    return_value=user_contact
                ):
            result = create_data._find_first_contact(
                self.supplier, "user@yopmail.com", "user@yopmail.com"
            )

        self.assertEqual(result, user_contact)

    def test_uses_orphan_contact_by_email(self):
        orphan = ContactStub("orphan", email_ids=[EmailStub("user@yopmail.com")])
        with patch.object(create_data, 'get_dynamic_link', return_value=[]), \
                patch.object(
                    create_data.frappe.db, 'sql',
                    return_value=[("orphan",)]
                ), \
                patch.object(create_data.frappe, 'get_doc', return_value=orphan):
            result = create_data._find_first_contact(
                self.supplier, "user@yopmail.com", None
            )

        self.assertEqual(result, orphan)


class TestRemoveOrphanDuplicates(unittest.TestCase):

    def setUp(self):
        mock_frappe.reset_mock()
        self.supplier = SimpleNamespace(doctype="Supplier", name="805026744", supplier_name="BANDAS CORREAS INDUSTRIALES SAS")

    def test_deletes_only_no_link_orphans(self):
        kept = ContactStub("kept", user="user@yopmail.com")
        orphan = ContactStub("orphan", user="user@yopmail.com")
        linked = ContactStub(
            "linked", user="user@yopmail.com",
            links=[LinkStub("Supplier", "otro")]
        )

        def fake_get_doc(doctype, name):
            return {"kept": kept, "orphan": orphan, "linked": linked}[name]

        rows = [("kept",), ("orphan",), ("linked",)]
        with patch.object(
            create_data.frappe.db, 'sql', return_value=rows
        ), patch.object(create_data.frappe, 'get_doc', side_effect=fake_get_doc):
            create_data._remove_orphan_contact_duplicates(
                "user@yopmail.com", kept
            )

        create_data.frappe.delete_doc.assert_called_once_with(
            "Contact", "orphan", ignore_permissions=True
        )


class TestCreateFirstContact(unittest.TestCase):

    def setUp(self):
        mock_frappe.reset_mock()
        self.supplier = SimpleNamespace(doctype="Supplier", name="805026744", supplier_name="BANDAS CORREAS INDUSTRIALES SAS")
        self.supplier_contact = ContactStub(
            "2545-805029159",
            email_ids=[EmailStub("user@yopmail.com")],
            links=[LinkStub("Supplier", "805026744")],
        )

    def test_reuses_supplier_contact_with_matching_email(self):
        with patch.object(
            create_data, 'get_dynamic_link',
            return_value=[self.supplier_contact]
        ), patch.object(
            create_data, '_remove_orphan_contact_duplicates'
        ) as cleanup_mock:
            result = create_data.create_first_contact(
                self.supplier, email="user@yopmail.com"
            )

        self.assertEqual(result, self.supplier_contact)
        self.assertEqual(self.supplier_contact.saved, 1)
        self.assertIn(
            "Supplier:805026744",
            [link.link_doctype + ":" + link.link_name
             for link in self.supplier_contact.links]
        )
        self.assertEqual(
            len([e for e in self.supplier_contact.email_ids]),
            1
        )
        cleanup_mock.assert_called_once()

    def test_creates_new_contact_when_no_matching_exists(self):
        new_contact = ContactStub("TECNOHERRAMIENTAS SAS-805029159")
        with patch.object(create_data, 'get_dynamic_link', return_value=[]), \
                patch.object(
                    create_data.frappe.db, 'exists', return_value=True
                ), \
                patch.object(
                    create_data.frappe, 'get_value', return_value=None
                ), \
                patch.object(
                    create_data.frappe.db, 'sql', return_value=[]
                ), \
                patch.object(
                    create_data.frappe, 'new_doc', return_value=new_contact
                ), \
                patch.object(
                    create_data, '_remove_orphan_contact_duplicates'
                ):
            result = create_data.create_first_contact(
                self.supplier, email="user@yopmail.com"
            )

        self.assertEqual(result, new_contact)
        self.assertEqual(new_contact.inserted, 1)
        self.assertEqual(new_contact.first_name, self.supplier.supplier_name)
        self.assertEqual(len(new_contact.links), 1)


if __name__ == '__main__':
    unittest.main()