# -*- coding: utf-8 -*-
"""
test_auto_assign_config_cache.py
================================
Regresion de performance de la asignacion automatica: la configuracion de
asignacion (qp_SP_OCType + qp_SP_AssignmentConfig y sus hijos) debe leerse UNA
vez por corrida y reutilizarse para todas las facturas, en lugar de recargarse
por cada factura (N+1 medido en produccion: ~1.240 consultas por factura).

Tambien cubre que `add_assignees` no reescriba la linea cuando no hay usuarios
nuevos.

Frappe se inyecta en sys.modules como mock (sin base de datos).
Ejecutar con: python -m pytest qp_supplier_front/tests/test_auto_assign_config_cache.py -v
"""
import sys
import unittest
from functools import partial
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()
sys.modules["frappe.model"] = MagicMock()
sys.modules["frappe.model.document"] = MagicMock()

from qp_supplier_front.resources.documenteme import auto_assign as infra  # noqa: E402

OC_TYPE_ROWS = [
    {"name": "01", "oc_type": "01 INFRAESTRUCTURA", "is_inventariable": 1},
    {"name": "03", "oc_type": "03 IT Y EQUIPOS", "is_inventariable": 0},
]

ASSIGNMENT_ROWS = [
    {"headquarter": "BOG", "oc_type": "01", "invoice_type": "Contado",
     "user_emails": ["a@x.com"], "user_preferences": {"a@x.com": "Ambos"},
     "user_roles": []},
    {"headquarter": "", "oc_type": "", "invoice_type": "Contado",
     "user_emails": ["catch@x.com"], "user_preferences": {},
     "user_roles": []},
]


class TestAssignmentConfigCache(unittest.TestCase):

    def _frappe(self, rows=None):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = rows if rows is not None else OC_TYPE_ROWS
        return frappe_mock

    def test_carga_config_una_vez_para_muchas_facturas(self):
        frappe_mock = self._frappe()
        load_calls = []

        def fake_load(oc_type_records=None):
            load_calls.append(oc_type_records)
            return ASSIGNMENT_ROWS

        with patch.object(infra, "frappe", frappe_mock), \
                patch.object(infra, "_load_assignment_rows", side_effect=fake_load), \
                patch.object(infra, "sede_exists", return_value=True):
            cache = infra.new_assignment_cache()
            results = [
                infra.get_assignee_emails(
                    None, None, has_receipt=False,
                    invoice_type="Contado", cache=cache)
                for _ in range(25)
            ]

        self.assertEqual(len(load_calls), 1)
        self.assertEqual(results, [["catch@x.com"]] * 25)
        oc_type_calls = [
            call for call in frappe_mock.get_all.call_args_list
            if call[0] and call[0][0] == "qp_SP_OCType"
        ]
        self.assertEqual(len(oc_type_calls), 1)

    def test_sin_cache_conserva_carga_por_llamada(self):
        frappe_mock = self._frappe()
        load_calls = []

        def fake_load(oc_type_records=None):
            load_calls.append(1)
            return ASSIGNMENT_ROWS

        with patch.object(infra, "frappe", frappe_mock), \
                patch.object(infra, "_load_assignment_rows", side_effect=fake_load), \
                patch.object(infra, "sede_exists", return_value=True):
            for _ in range(3):
                infra.get_assignee_emails(
                    None, None, has_receipt=False, invoice_type="Contado")

        self.assertEqual(len(load_calls), 3)

    def test_cada_corrida_usa_su_propio_cache(self):
        frappe_mock = self._frappe()
        load_calls = []

        def fake_load(oc_type_records=None):
            load_calls.append(1)
            return ASSIGNMENT_ROWS

        with patch.object(infra, "frappe", frappe_mock), \
                patch.object(infra, "_load_assignment_rows", side_effect=fake_load), \
                patch.object(infra, "sede_exists", return_value=True):
            for _ in range(2):
                cache = infra.new_assignment_cache()
                infra.get_assignee_emails(
                    None, None, has_receipt=False,
                    invoice_type="Contado", cache=cache)

        self.assertEqual(len(load_calls), 2)

    def test_roles_se_resuelven_una_vez_por_conjunto(self):
        rows = [dict(ASSIGNMENT_ROWS[0], user_roles=["Alpla Finanzas"])]
        frappe_mock = self._frappe()
        role_calls = []

        def fake_roles(roles):
            role_calls.append(list(roles))
            return ["rol@x.com"]

        with patch.object(infra, "frappe", frappe_mock), \
                patch.object(infra, "_load_assignment_rows", return_value=rows), \
                patch.object(infra, "resolve_role_users", side_effect=fake_roles), \
                patch.object(infra, "sede_exists", return_value=True):
            cache = infra.new_assignment_cache()
            for _ in range(4):
                infra.get_assignee_emails(
                    "01", "BOG", has_receipt=True,
                    invoice_type="Contado", cache=cache)

        self.assertEqual(len(role_calls), 1)
        self.assertEqual(role_calls[0], ["Alpla Finanzas"])

    def test_sin_cache_no_memoiza_roles(self):
        rows = [dict(ASSIGNMENT_ROWS[0], user_roles=["Alpla Finanzas"])]
        frappe_mock = self._frappe()
        role_calls = []

        def fake_roles(roles):
            role_calls.append(list(roles))
            return ["rol@x.com"]

        with patch.object(infra, "frappe", frappe_mock), \
                patch.object(infra, "_load_assignment_rows", return_value=rows), \
                patch.object(infra, "resolve_role_users", side_effect=fake_roles), \
                patch.object(infra, "sede_exists", return_value=True):
            for _ in range(2):
                infra.get_assignee_emails(
                    "01", "BOG", has_receipt=True, invoice_type="Contado")

        self.assertEqual(len(role_calls), 2)


class TestRunAutoAssignCacheWiring(unittest.TestCase):

    def _capture_core_kwargs(self):
        captured = {}

        def fake_core(**kwargs):
            captured.update(kwargs)
            return []

        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.side_effect = lambda doctype, field: {
            "assign_invoices_without_po": 0,
            "documenteme_backend": "BC",
        }.get(field)
        frappe_mock.get_all.return_value = OC_TYPE_ROWS

        with patch.object(infra, "frappe", frappe_mock), \
                patch.object(infra, "auto_assign_core", side_effect=fake_core):
            infra.run_auto_assign(["SL1"])

        return captured, frappe_mock

    def test_pasa_resolver_con_cache_de_corrida(self):
        captured, _ = self._capture_core_kwargs()
        resolver = captured["resolve_emails_fn"]

        self.assertIsInstance(resolver, partial)
        self.assertIsInstance(resolver.keywords.get("cache"), dict)

    def test_el_resolver_inyectado_carga_la_config_una_sola_vez(self):
        captured, frappe_mock = self._capture_core_kwargs()
        resolver = captured["resolve_emails_fn"]
        load_calls = []

        def fake_load(oc_type_records=None):
            load_calls.append(1)
            return ASSIGNMENT_ROWS

        with patch.object(infra, "_load_assignment_rows", side_effect=fake_load), \
                patch.object(infra, "sede_exists", return_value=True):
            for _ in range(10):
                resolver(None, None, has_receipt=False, invoice_type="Contado")

        self.assertEqual(len(load_calls), 1)


class TestAddAssigneesNoOpSave(unittest.TestCase):

    def _line(self, users):
        line = MagicMock()
        line.assigned_users = [
            type("Row", (), {"user": user})() for user in users
        ]
        return line

    def test_no_guarda_si_el_usuario_ya_esta(self):
        line = self._line(["a@x.com"])
        frappe_mock = MagicMock()
        frappe_mock.get_doc.return_value = line

        with patch.object(infra, "frappe", frappe_mock):
            infra.add_assignees("SL1", ["a@x.com"])

        line.save.assert_not_called()
        line.append.assert_not_called()

    def test_guarda_una_vez_y_solo_los_nuevos(self):
        line = self._line(["a@x.com"])
        frappe_mock = MagicMock()
        frappe_mock.get_doc.return_value = line

        with patch.object(infra, "frappe", frappe_mock):
            infra.add_assignees("SL1", ["a@x.com", "b@x.com", "b@x.com"])

        line.save.assert_called_once()
        line.append.assert_called_once_with(
            "assigned_users", {"user": "b@x.com"})


class TestCollectionUsesOwnCache(unittest.TestCase):

    def test_collection_inyecta_cache_de_corrida(self):
        from qp_supplier_front.resources.collection_accounts import (
            auto_assign as collection,
        )

        captured = {}

        def fake_core(**kwargs):
            captured.update(kwargs)
            return []

        with patch.object(collection, "auto_assign_core", side_effect=fake_core):
            collection.run_collection_auto_assign()

        resolver = captured["resolve_emails_fn"]
        self.assertIsInstance(resolver, partial)
        self.assertIsInstance(resolver.keywords.get("cache"), dict)


if __name__ == "__main__":
    unittest.main()
