# -*- coding: utf-8 -*-
"""
test_admin_repair_endpoint.py
==============================
Pruebas unitarias del endpoint GET de reparacion de contactos primarios
(resources/admin/repair_primary_contacts.py).
Aisladas de la base de datos y de Frappe usando mocks de sys.modules.

Ejecutar con: python3 -m unittest qp_supplier_front/tests/test_admin_repair_endpoint.py -v
"""
import sys
from unittest.mock import MagicMock, patch

mock_frappe = MagicMock()
sys.modules['frappe'] = mock_frappe


def _identity_decorator(*args, **kwargs):
    return lambda fn: fn


mock_frappe.whitelist.side_effect = _identity_decorator

import unittest

import qp_supplier_front.resources.admin.repair_primary_contacts as endpoint
from qp_supplier_front.resources.admin.repair_primary_contacts import run


class TestAdminRepairEndpoint(unittest.TestCase):

    def setUp(self):
        mock_frappe.reset_mock()
        mock_frappe.response = {}
        self.run_repair_patcher = patch.object(endpoint, "run_repair")
        self.mock_run_repair = self.run_repair_patcher.start()
        self.mock_run_repair.return_value = [
            {"supplier": "SUP-1", "action": "restaurar_primario"}
        ]

    def tearDown(self):
        self.run_repair_patcher.stop()

    def test_non_admin_gets_403(self):
        mock_frappe.session.user = "supplier@example.com"
        mock_frappe.get_roles.return_value = ["Supplier"]

        run(dry_run=1)

        self.assertEqual(mock_frappe.response["http_status_code"], 403)
        self.assertFalse(self.mock_run_repair.called)

    def test_admin_dry_run_calls_repair_and_reports(self):
        mock_frappe.session.user = "Administrator"
        mock_frappe.get_roles.return_value = ["Administrator"]

        run(dry_run=1)

        self.mock_run_repair.assert_called_once_with(dry_run=True)
        self.assertEqual(mock_frappe.response["http_status_code"], 200)
        data = mock_frappe.response["message"]["data"]
        self.assertEqual(data[0]["supplier"], "SUP-1")

    def test_admin_apply_calls_repair_with_dry_run_false(self):
        mock_frappe.session.user = "Administrator"
        mock_frappe.get_roles.return_value = ["Administrator"]

        run(dry_run=0)

        self.mock_run_repair.assert_called_once_with(dry_run=False)

    def test_admin_handles_error(self):
        mock_frappe.session.user = "Administrator"
        mock_frappe.get_roles.return_value = ["Administrator"]
        self.mock_run_repair.side_effect = Exception("boom")

        run(dry_run=1)

        self.assertEqual(mock_frappe.response["http_status_code"], 500)

    def test_dry_run_defaults_to_true(self):
        mock_frappe.session.user = "Administrator"
        mock_frappe.get_roles.return_value = ["Administrator"]

        run(dry_run="")

        self.mock_run_repair.assert_called_once_with(dry_run=True)


if __name__ == "__main__":
    unittest.main()