# -*- coding: utf-8 -*-
"""
test_documenteme_assign_infra.py
================================
Pruebas unitarias para el endpoint de asignacion manual de documenteme
(resources/documenteme/assign.py): normalizacion de la lista de usuarios,
compatibilidad con el parametro legacy `user` y validacion de usuarios.

Frappe se inyecta en sys.modules como mock (sin base de datos).
Ejecutar con: python -m unittest qp_supplier_front.tests.test_documenteme_assign_infra -v
"""
import json
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()
sys.modules["frappe.model"] = MagicMock()
sys.modules["frappe.model.document"] = MagicMock()

# El decorador real de frappe no existe en el mock: devolvemos la funcion tal
# cual para poder invocar el endpoint desde los tests.
sys.modules["frappe"].whitelist = lambda *args, **kwargs: (lambda fn: fn)

from qp_supplier_front.resources.documenteme import assign as infra  # noqa: E402


class TestRequestedUsers(unittest.TestCase):

    def _requested(self, users=None, user=None):
        with patch.object(infra, "parse_json", side_effect=json.loads):
            return infra._requested_users(users, user)

    def test_usuario_legacy_unico(self):
        self.assertEqual(["a@x.com"], self._requested(user="a@x.com"))

    def test_lista_json_de_usuarios(self):
        self.assertEqual(
            ["a@x.com", "b@x.com"],
            self._requested('["a@x.com", "b@x.com"]'),
        )

    def test_combina_users_y_user_sin_duplicar(self):
        self.assertEqual(
            ["a@x.com", "b@x.com"],
            self._requested('["a@x.com"]', user="b@x.com"),
        )

    def test_sin_usuarios_retorna_vacio(self):
        self.assertEqual([], self._requested())

    def test_descarta_vacios_y_duplicados(self):
        self.assertEqual(
            ["a@x.com", "b@x.com"],
            self._requested('["a@x.com", "", "a@x.com", "b@x.com"]'),
        )

    def test_string_plano_no_json_se_acepta(self):
        self.assertEqual(["a@x.com"], self._requested("a@x.com"))


class TestInvalidUsers(unittest.TestCase):

    def test_usuario_existente_y_habilitado(self):
        with patch.object(infra.frappe.db, "exists", return_value=True), \
                patch.object(infra.frappe.db, "get_value", return_value=1):
            self.assertEqual([], infra._invalid_users(["a@x.com"]))

    def test_usuario_inexistente(self):
        with patch.object(infra.frappe.db, "exists", return_value=False):
            self.assertEqual(["a@x.com"], infra._invalid_users(["a@x.com"]))

    def test_usuario_deshabilitado(self):
        with patch.object(infra.frappe.db, "exists", return_value=True), \
                patch.object(infra.frappe.db, "get_value", return_value=0):
            self.assertEqual(["a@x.com"], infra._invalid_users(["a@x.com"]))


if __name__ == "__main__":
    unittest.main()

class TestAssignEndpointTimeline(unittest.TestCase):

    def _run(self, users='["new@x.com"]', previous=None, allowed=True):
        frappe_mock = MagicMock()
        frappe_mock.session.user = "author@x.com"
        names = {
            "old@x.com": "Viejo",
            "new@x.com": "Nuevo",
            "new2@x.com": "Nuevo2",
        }

        def _get_value(doctype, name, field, *args, **kwargs):
            if doctype == "qp_SP_DocumentDetail":
                return "SL-1"
            return names.get(name, name)

        frappe_mock.db.get_value.side_effect = _get_value
        response_mock = MagicMock()
        timeline = MagicMock()

        patches = [
            patch.object(infra, "frappe", frappe_mock),
            patch.object(infra, "parse_json", side_effect=json.loads),
            patch.object(infra, "can_reassign_documenteme", return_value=allowed),
            patch.object(infra, "_invalid_users", return_value=[]),
            patch.object(infra, "_assigned_users", return_value=previous or []),
            patch.object(infra, "assign_documents"),
            patch.object(infra, "response", response_mock),
            patch.object(infra, "RealTimelineAdapter", return_value=timeline),
        ]
        started = []
        try:
            for item in patches:
                item.start()
                started.append(item)
            infra.assign('["DOC-1"]', users=users)
        finally:
            for item in reversed(started):
                item.stop()

        return frappe_mock, response_mock, timeline

    def test_registra_historial_con_previos_y_autor(self):
        _, response_mock, timeline = self._run(previous=["old@x.com"])

        args, kwargs = timeline.add_user_assignment.call_args
        self.assertEqual(args[0], "DOC-1")
        self.assertEqual(
            args[1], "Asignados: Nuevo. Asignados previos: Viejo.")
        self.assertEqual(kwargs["user"], "author@x.com")
        self.assertEqual(response_mock.call_args[0][0], 200)

    def test_registra_historial_sin_previos(self):
        _, _, timeline = self._run()

        message = timeline.add_user_assignment.call_args[0][1]
        self.assertEqual(message, "Asignados: Nuevo.")

    def test_sin_rol_de_reasignacion_devuelve_403(self):
        frappe_mock, response_mock, timeline = self._run(allowed=False)

        self.assertEqual(response_mock.call_args[0][0], 403)
        timeline.add_user_assignment.assert_not_called()
        frappe_mock.db.commit.assert_not_called()

    def test_asigna_varios_y_registra_todos(self):
        _, _, timeline = self._run(users='["new@x.com", "new2@x.com"]')

        args, _ = timeline.add_user_assignment.call_args
        self.assertEqual(
            args[1], "Asignados: Nuevo, Nuevo2.")

class TestAssignEndpointsPermission(unittest.TestCase):

    def _run(self, fn, *args, **kwargs):
        frappe_mock = MagicMock()
        frappe_mock.get_roles.return_value = ["Administrador Sede Documenteme"]
        response_mock = MagicMock()
        with patch.object(infra, "frappe", frappe_mock), \
                patch.object(infra, "response", response_mock):
            fn(*args, **kwargs)
        return frappe_mock, response_mock

    def test_get_users_403_sin_rol_de_reasignacion(self):
        frappe_mock, response_mock = self._run(infra.get_users)
        self.assertEqual(response_mock.call_args[0][0], 403)
        frappe_mock.get_all.assert_not_called()

    def test_get_document_data_403_sin_rol_de_reasignacion(self):
        _, response_mock = self._run(infra.get_document_data, '["DOC-1"]')
        self.assertEqual(response_mock.call_args[0][0], 403)

    def test_assign_403_sin_rol_de_reasignacion(self):
        frappe_mock, response_mock = self._run(
            infra.assign, '["DOC-1"]', users='["new@x.com"]')
        self.assertEqual(response_mock.call_args[0][0], 403)
        frappe_mock.db.commit.assert_not_called()

    def test_assign_permite_compras(self):
        frappe_mock = MagicMock()
        frappe_mock.get_roles.return_value = ["Administrador Compras Documenteme"]
        frappe_mock.db.get_value.return_value = "SL-1"
        response_mock = MagicMock()
        with patch.object(infra, "frappe", frappe_mock), \
                patch.object(infra, "parse_json", side_effect=json.loads), \
                patch.object(infra, "_invalid_users", return_value=[]), \
                patch.object(infra, "_assigned_users", return_value=[]), \
                patch.object(infra, "_display_names", return_value=["Nuevo"]), \
                patch.object(infra, "assign_documents"), \
                patch.object(infra, "RealTimelineAdapter"), \
                patch.object(infra, "response", response_mock):
            infra.assign('["DOC-1"]', users='["new@x.com"]')
        self.assertEqual(response_mock.call_args[0][0], 200)

