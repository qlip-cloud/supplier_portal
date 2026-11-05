# -*- coding: utf-8 -*-
"""
test_sede_source.py
===================
Pruebas unitarias para services/sede_source.py:
  - get_sede_source_doctype: lee el origen configurado con fallback al default.
  - sede_exists: valida que una sede exista en el doctype fuente configurado.

Frappe se inyecta en sys.modules como mock (sin base de datos).
Ejecutar con: python -m pytest qp_supplier_front/tests/test_sede_source.py -v
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()

from qp_supplier_front.services import sede_source  # noqa: E402


class TestGetSedeSourceDoctype(unittest.TestCase):

    def _run(self, frappe_mock):
        with patch.object(sede_source, "frappe", frappe_mock):
            return sede_source.get_sede_source_doctype()

    def test_lee_el_valor_configurado(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = "qp_md_headquarter"

        self.assertEqual(self._run(frappe_mock), "qp_md_headquarter")
        frappe_mock.db.get_single_value.assert_called_once_with(
            "qp_SP_MasterSetup", "sede_source_doctype"
        )

    def test_vacio_usa_el_default(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = ""

        self.assertEqual(self._run(frappe_mock), "qp_md_headquarter")

    def test_sin_valor_usa_el_default(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = None

        self.assertEqual(self._run(frappe_mock), "qp_md_headquarter")


class TestSedeExists(unittest.TestCase):

    def _run(self, frappe_mock, sede_code):
        with patch.object(sede_source, "frappe", frappe_mock):
            return sede_source.sede_exists(sede_code)

    def test_sede_existe_por_code(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = "qp_md_headquarter"
        frappe_mock.db.exists.side_effect = [True, True, True]

        self.assertTrue(self._run(frappe_mock, "101"))
        frappe_mock.db.exists.assert_any_call("qp_md_headquarter", {"code": "101"})

    def test_sede_no_existe(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = "qp_md_headquarter"
        frappe_mock.db.exists.side_effect = [True, False, False]

        self.assertFalse(self._run(frappe_mock, "999"))

    def test_codigo_vacio_retorna_false(self):
        self.assertFalse(self._run(MagicMock(), None))

    def test_doctype_fuente_inexistente_retorna_false(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = "qp_md_headquarter"
        frappe_mock.db.exists.side_effect = [False]

        self.assertFalse(self._run(frappe_mock, "101"))


class TestListSedes(unittest.TestCase):

    def _run(self, frappe_mock):
        with patch.object(sede_source, "frappe", frappe_mock):
            return sede_source.list_sedes()

    def test_retorna_las_sedes_del_origen(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = "qp_md_headquarter"
        frappe_mock.db.exists.return_value = True
        frappe_mock.get_all.return_value = [
            {"code": "BOG", "title": "Bogota"},
            {"code": "CAL", "title": "Cali"},
        ]

        result = self._run(frappe_mock)

        self.assertEqual(result, [
            {"code": "BOG", "title": "Bogota"},
            {"code": "CAL", "title": "Cali"},
        ])
        frappe_mock.get_all.assert_called_once_with(
            "qp_md_headquarter",
            fields=["code", "title"],
            order_by="title asc",
        )

    def test_doctype_fuente_inexistente_retorna_lista_vacia(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = "qp_md_headquarter"
        frappe_mock.db.exists.return_value = False

        self.assertEqual(self._run(frappe_mock), [])

    def test_sin_origen_retorna_lista_vacia(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_single_value.return_value = ""
        frappe_mock.db.exists.return_value = False

        self.assertEqual(self._run(frappe_mock), [])


if __name__ == "__main__":
    unittest.main()
