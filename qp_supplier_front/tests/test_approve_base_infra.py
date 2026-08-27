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
from contextlib import ExitStack
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


class TestMarkDuplicateRegistered(unittest.TestCase):

    NOW = "2026-08-12 10:00:00"

    ERROR = "Error Ya existe la factura de compra SETT0501165 para este proveedor"

    def _patched(self, frappe_mock):
        stack = ExitStack()
        self.addCleanup(stack.close)
        return {
            "frappe": stack.enter_context(patch.object(infra, "frappe", frappe_mock)),
            "resolve_open_alerts": stack.enter_context(patch.object(infra, "resolve_open_alerts")),
            "insert_alert": stack.enter_context(patch.object(infra, "insert_alert")),
            "persist_invoice": stack.enter_context(patch.object(infra, "persist_invoice")),
            "mark_registered": stack.enter_context(patch.object(infra, "mark_registered")),
        }

    def test_marca_bcc_resuelve_y_alerta_con_error(self):
        frappe_mock = MagicMock()
        doc = {"name": "DOC1", "nvfac_nume": "FAC001"}
        mocks = self._patched(frappe_mock)
        infra.mark_duplicate_registered(doc, self.ERROR, self.NOW)

        frappe_mock.db.set_value.assert_called_once_with(
            "qp_SP_DocumentDetail", "DOC1", "nvfac_esta", "BCC"
        )
        self.assertEqual(doc["nvfac_esta"], "BCC")
        mocks["resolve_open_alerts"].assert_called_once_with("DOC1")

        mocks["insert_alert"].assert_called_once()
        parent, message, now_arg = mocks["insert_alert"].call_args[0]
        self.assertEqual(parent, "DOC1")
        self.assertEqual(now_arg, self.NOW)
        self.assertIn("se detuvo el reintento", message)
        self.assertIn("No se pudo obtener el codigo BC", message)
        self.assertIn(self.ERROR, message)

    def test_no_crea_referencia_ni_marca_registrado(self):
        frappe_mock = MagicMock()
        doc = {"name": "DOC1", "nvfac_nume": "FAC001"}
        mocks = self._patched(frappe_mock)
        infra.mark_duplicate_registered(doc, self.ERROR, self.NOW)

        mocks["persist_invoice"].assert_not_called()
        mocks["mark_registered"].assert_not_called()


if __name__ == "__main__":
    unittest.main()