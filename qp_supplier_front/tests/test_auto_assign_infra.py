# -*- coding: utf-8 -*-
"""
test_auto_assign_infra.py
==========================
Pruebas unitarias para los callbacks de infraestructura de la asignacion
automatica (resources/documenteme/auto_assign.py):
  - get_receipt_total: suma el total de Purchase Receipt por qp_supplier_oc.
  - get_oc_context: valida la cadena nvfac_orde == qp_order_confirmation_no.

Frappe se inyecta en sys.modules como mock (sin base de datos).
Ejecutar con: python -m pytest qp_supplier_front/tests/test_auto_assign_infra.py -v
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules["frappe"] = MagicMock()

from qp_supplier_front.resources.documenteme import auto_assign as infra  # noqa: E402


class TestGetReceiptTotal(unittest.TestCase):

    def _run(self, frappe_mock, purchase_order_number):
        with patch.object(infra, "frappe", frappe_mock):
            return infra.get_receipt_total(purchase_order_number)

    def test_suma_totales_de_purchase_receipt_por_supplier_oc(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = [{"total": 400}, {"total": 600}]

        total = self._run(frappe_mock, "OC111")

        self.assertEqual(total, 1000)
        frappe_mock.get_all.assert_called_once_with(
            "Purchase Receipt",
            filters={"qp_supplier_oc": "OC111"},
            fields=["total"],
        )

    def test_sin_recibos_retorna_none(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = []
        self.assertIsNone(self._run(frappe_mock, "OC111"))

    def test_sin_oc_retorna_none(self):
        self.assertIsNone(self._run(MagicMock(), None))

    def test_recibos_sin_total_no_rompen_la_suma(self):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = [{"total": None}, {"total": 200}]
        self.assertEqual(self._run(frappe_mock, "OC111"), 200)


class TestGetOCContext(unittest.TestCase):

    def _mock_frappe(self, po_exists=True, values=None):
        frappe_mock = MagicMock()
        frappe_mock.db.exists.return_value = po_exists
        frappe_mock.db.get_value.return_value = values or (
            "01", "BOG", "OC111"
        )
        return frappe_mock

    def _run(self, frappe_mock, purchase_order_number):
        with patch.object(infra, "frappe", frappe_mock):
            return infra.get_oc_context(purchase_order_number)

    def test_devuelve_contexto_cuando_cadena_coincide(self):
        frappe_mock = self._mock_frappe()
        ctx = self._run(frappe_mock, "OC111")
        self.assertEqual(ctx, {"oc_type": "01", "headquarter": "BOG"})

    def test_sin_oc_retorna_none(self):
        self.assertIsNone(self._run(self._mock_frappe(), None))

    def test_oc_inexistente_retorna_none(self):
        frappe_mock = self._mock_frappe(po_exists=False)
        self.assertIsNone(self._run(frappe_mock, "OC111"))

    def test_cadena_rota_retorna_none(self):
        frappe_mock = self._mock_frappe(values=("01", "BOG", "OC999"))
        self.assertIsNone(self._run(frappe_mock, "OC111"))


if __name__ == "__main__":
    unittest.main()
