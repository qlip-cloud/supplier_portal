# -*- coding: utf-8 -*-
"""
test_odata.py
==============
Pruebas unitarias para infrastructure/strategies/bc/odata.py
(Normalizacion de fechas a literal OData Edm.Date).
Aisladas de Frappe y de la base de datos.
Ejecutar con: python -m unittest qp_supplier_front.tests.test_odata -v
"""
import unittest
from datetime import date, datetime

from qp_supplier_front.infrastructure.strategies.bc.odata import to_odata_date


class TestToOdataDate(unittest.TestCase):

    def test_datetime_returns_date_only(self):
        self.assertEqual(to_odata_date(datetime(2026, 8, 5, 0, 0, 0)), "2026-08-05")

    def test_datetime_with_time_returns_date_only(self):
        self.assertEqual(to_odata_date(datetime(2026, 8, 5, 14, 30, 0)), "2026-08-05")

    def test_date_returns_date_only(self):
        self.assertEqual(to_odata_date(date(2026, 8, 5)), "2026-08-05")

    def test_string_with_time_returns_date_only(self):
        self.assertEqual(to_odata_date("2026-08-05 00:00:00"), "2026-08-05")

    def test_date_string_returns_unchanged(self):
        self.assertEqual(to_odata_date("2026-08-06"), "2026-08-06")

    def test_none_returns_empty(self):
        self.assertEqual(to_odata_date(None), "")


if __name__ == "__main__":
    unittest.main()
