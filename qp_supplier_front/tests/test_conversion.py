# -*- coding: utf-8 -*-
"""
test_conversion.py
==================
Pruebas unitarias para el helper puro de diferenciacion
Credito/Contado de facturas documenteme.

Ejecutar con: python -m pytest qp_supplier_front/tests/test_conversion.py -v
"""
import unittest

from qp_supplier_front.uses_cases.documenteme.conversion import (
    CONTADO,
    CREDITO,
    is_cash_invoice,
)


class TestIsCashInvoice(unittest.TestCase):

    def test_contado_es_cash(self):
        self.assertTrue(is_cash_invoice(CONTADO))

    def test_credito_no_es_cash(self):
        self.assertFalse(is_cash_invoice(CREDITO))

    def test_vacio_no_es_cash(self):
        self.assertFalse(is_cash_invoice(None))
        self.assertFalse(is_cash_invoice(""))

    def test_numerico_contado_es_cash(self):
        self.assertTrue(is_cash_invoice(1))

    def test_otros_valores_no_son_cash(self):
        self.assertFalse(is_cash_invoice("0"))
        self.assertFalse(is_cash_invoice("3"))
        self.assertFalse(is_cash_invoice("x"))


if __name__ == "__main__":
    unittest.main()
