# -*- coding: utf-8 -*-
"""
test_approve_base_infra.py
==========================
Pruebas unitarias para los callbacks de infraestructura nuevos de la
aprobacion documenteme (resources/documenteme/_approve_base.py):
  - get_headquarter: resuelve qp_headquarter de la Purchase Order vinculada.

Frappe se inyecta en sys.modules como mock (sin base de datos).
Ejecutar con: python -m pytest qp_supplier_front/tests/test_approve_base_infra.py -v
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()

from qp_supplier_front.resources.documenteme import _approve_base as infra  # noqa: E402


class TestGetHeadquarter(unittest.TestCase):

    def _run(self, frappe_mock, purchase_order):
        with patch.object(infra, "frappe", frappe_mock):
            return infra.get_headquarter(purchase_order)

    def test_sin_oc_retorna_cadena_vacia(self):
        self.assertEqual(self._run(MagicMock(), ""), "")
        self.assertEqual(self._run(MagicMock(), None), "")

    def test_sin_oc_no_consulta_la_purchase_order(self):
        frappe_mock = MagicMock()
        self._run(frappe_mock, "")
        frappe_mock.db.get_value.assert_not_called()

    def test_con_oc_devuelve_qp_headquarter(self):
        frappe_mock = MagicMock()
        frappe_mock.db.get_value.return_value = "HQ01"
        self.assertEqual(self._run(frappe_mock, "OC111"), "HQ01")
        frappe_mock.db.get_value.assert_called_once_with(
            "Purchase Order", "OC111", "qp_headquarter"
        )

    def test_headquarter_none_o_vacio_devuelve_cadena_vacia(self):
        for value in (None, ""):
            frappe_mock = MagicMock()
            frappe_mock.db.get_value.return_value = value
            self.assertEqual(self._run(frappe_mock, "OC111"), "")


if __name__ == "__main__":
    unittest.main()