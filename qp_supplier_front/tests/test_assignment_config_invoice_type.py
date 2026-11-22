# -*- coding: utf-8 -*-
"""
test_assignment_config_invoice_type.py
======================================
Validacion del campo `invoice_type` de `qp_SP_AssignmentConfig`:

- La fila sin OC (oc_type y headquarter vacios) exige `Credito` o `Contado`.
- Un valor vacio/desconocido se normaliza a `Todos`.
- Las filas con OC no exigen tipo de factura.

Ejecutar con: python -m unittest qp_supplier_front.tests.test_assignment_config_invoice_type -v
"""
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import qp_supplier_front.qp_supplier_front.doctype.qp_sp_assignmentconfig.qp_sp_assignmentconfig as module


def _doc(**fields):
    data = {"oc_type": "", "headquarter": "", "invoice_type": ""}
    data.update(fields)
    return SimpleNamespace(**data)


class TestAssignmentConfigInvoiceType(unittest.TestCase):

    def test_catch_all_exige_tipo_de_factura(self):
        doc = _doc()
        with patch.object(module, "frappe") as frappe_mock:
            module.qp_SP_AssignmentConfig.validate(doc)
        self.assertEqual(doc.invoice_type, "Todos")
        frappe_mock.throw.assert_called_once()

    def test_catch_all_credito(self):
        doc = _doc(invoice_type="Credito")
        with patch.object(module, "frappe") as frappe_mock:
            module.qp_SP_AssignmentConfig.validate(doc)
        self.assertEqual(doc.invoice_type, "Credito")
        frappe_mock.throw.assert_not_called()

    def test_catch_all_contado(self):
        doc = _doc(invoice_type="Contado")
        with patch.object(module, "frappe") as frappe_mock:
            module.qp_SP_AssignmentConfig.validate(doc)
        self.assertEqual(doc.invoice_type, "Contado")
        frappe_mock.throw.assert_not_called()

    def test_valor_desconocido_se_normaliza(self):
        doc = _doc(invoice_type="Otro")
        with patch.object(module, "frappe") as frappe_mock:
            module.qp_SP_AssignmentConfig.validate(doc)
        self.assertEqual(doc.invoice_type, "Todos")
        frappe_mock.throw.assert_called_once()

    def test_no_aplica_es_wildcard(self):
        doc = _doc(oc_type="No aplica", invoice_type="")
        with patch.object(module, "frappe") as frappe_mock:
            module.qp_SP_AssignmentConfig.validate(doc)
        self.assertEqual(doc.invoice_type, "Todos")
        frappe_mock.throw.assert_not_called()

    def test_fila_con_oc_no_exige_tipo(self):
        doc = _doc(oc_type="01", headquarter="BOG", invoice_type="")
        with patch.object(module, "frappe") as frappe_mock:
            frappe_mock.get_all.return_value = []
            frappe_mock.db.get_value.return_value = None
            module.qp_SP_AssignmentConfig.validate(doc)
        self.assertEqual(doc.invoice_type, "Todos")
        frappe_mock.throw.assert_not_called()


if __name__ == "__main__":
    unittest.main()
