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
    NC_TIPO_DOCU,
    is_cash_invoice,
    is_credit_note,
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


class TestIsCreditNote(unittest.TestCase):

    def test_nc_es_nota_credito(self):
        self.assertTrue(is_credit_note(NC_TIPO_DOCU))

    def test_factura_no_es_nota_credito(self):
        self.assertFalse(is_credit_note("F"))
        self.assertFalse(is_credit_note("FAC"))
        self.assertFalse(is_credit_note("D"))
        self.assertFalse(is_credit_note("ND"))

    def test_vacio_no_es_nota_credito(self):
        self.assertFalse(is_credit_note(None))
        self.assertFalse(is_credit_note(""))

    def test_numerico_nc_es_nota_credito(self):
        self.assertTrue(is_credit_note("C"))

    def test_otras_letras_no_son_nc(self):
        self.assertFalse(is_credit_note("X"))
        self.assertFalse(is_credit_note("c"))


if __name__ == "__main__":
    unittest.main()
