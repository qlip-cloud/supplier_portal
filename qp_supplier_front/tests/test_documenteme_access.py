# -*- coding: utf-8 -*-
"""
test_documenteme_access.py
==========================
Pruebas unitarias para services/documenteme_access.py:

  - can_see_all_documenteme: roles que ven todas las facturas.
  - is_sede_documenteme: deteccion del rol sede.
  - get_assigned_sync_lines_filters: aplica la restriccion por asignacion
    (ve todo vs. solo asignadas).
  - get_assigned_sync_line_names: consulta sync lines asignadas al usuario.

Ejecutar con: python -m pytest qp_supplier_front/tests/test_documenteme_access.py -v
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()

from qp_supplier_front.services import documenteme_access  # noqa: E402


SEE_ALL = "Administrador Documenteme"
COMPRAS = "Administrador Compras Documenteme"
SEDE = "Administrador Sede Documenteme"


class TestCanSeeAllDocumenteme(unittest.TestCase):

    def test_administrador_documenteme_ve_todo(self):
        self.assertTrue(documenteme_access.can_see_all_documenteme([SEE_ALL]))

    def test_administrador_compras_ve_todo(self):
        self.assertTrue(documenteme_access.can_see_all_documenteme([COMPRAS]))

    def test_administrator_ve_todo(self):
        self.assertTrue(documenteme_access.can_see_all_documenteme(["Administrator"]))

    def test_sede_no_ve_todo(self):
        self.assertFalse(documenteme_access.can_see_all_documenteme([SEDE]))

    def test_sin_roles_no_ve_todo(self):
        self.assertFalse(documenteme_access.can_see_all_documenteme([]))

    def test_none_no_ve_todo(self):
        self.assertFalse(documenteme_access.can_see_all_documenteme(None))


class TestIsSedeDocumenteme(unittest.TestCase):

    def test_solo_sede_true(self):
        self.assertTrue(documenteme_access.is_sede_documenteme([SEDE]))

    def test_con_compras_no_es_sede(self):
        self.assertFalse(documenteme_access.is_sede_documenteme([COMPRAS, SEDE]))

    def test_sin_roles_false(self):
        self.assertFalse(documenteme_access.is_sede_documenteme([]))

    def test_none_false(self):
        self.assertFalse(documenteme_access.is_sede_documenteme(None))


class TestGetAssignedSyncLinesFilters(unittest.TestCase):

    def _run(self, user_roles, user, assigned_names, filters=None):
        return documenteme_access.get_assigned_sync_lines_filters(
            user_roles, user, lambda u: assigned_names, filters
        )

    def test_ve_todo_no_modifica_filtros(self):
        result = self._run([SEE_ALL], "user@x.com", ["L1"], {"nvpro_ndoc": "902"})
        self.assertEqual(result, {"nvpro_ndoc": "902"})

    def test_ve_todo_no_llama_asignadas(self):
        called = {"v": False}

        def assigned_fn(user):
            called["v"] = True
            return ["L1"]

        result = documenteme_access.get_assigned_sync_lines_filters(
            [SEE_ALL], "user@x.com", assigned_fn, {"nvpro_ndoc": "1"}
        )
        self.assertFalse(called["v"])
        self.assertEqual(result, {"nvpro_ndoc": "1"})

    def test_sede_con_asignadas_filtra_por_in(self):
        result = self._run([SEDE], "user@x.com", ["L1", "L2"], {"nvpro_ndoc": "1"})
        self.assertEqual(result["nvfac_nume"], ["in", ["L1", "L2"]])
        self.assertEqual(result["nvpro_ndoc"], "1")

    def test_sede_sin_asignadas_filtra_vacio(self):
        result = self._run([SEDE], "user@x.com", [], {"nvpro_ndoc": "1"})
        self.assertEqual(result["nvfac_nume"], ["in", []])

    def test_sin_filtros_base_agrega_filtro(self):
        result = self._run([SEDE], "user@x.com", ["L1"])
        self.assertEqual(result["nvfac_nume"], ["in", ["L1"]])

    def test_sede_no_mutafiltro_original(self):
        base = {"nvpro_ndoc": "1"}
        self._run([SEDE], "user@x.com", ["L1"], base)
        self.assertEqual(base, {"nvpro_ndoc": "1"})


class TestGetAssignedSyncLineNames(unittest.TestCase):

    def _run(self, frappe_mock):
        with patch.dict("sys.modules", {"frappe": frappe_mock}):
            return documenteme_access.get_assigned_sync_line_names("user@x.com")

    def test_combina_child_rows_y_assigned_to(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.side_effect = [
            [{"parent": "F1"}, {"parent": "F2"}],
            [{"name": "F2"}, {"name": "F3"}],
        ]

        result = self._run(frappe_mock)

        self.assertCountEqual(result, ["F1", "F2", "F3"])

    def test_sin_asignaciones_vacio(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.side_effect = [[], []]

        result = self._run(frappe_mock)

        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
