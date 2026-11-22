# -*- coding: utf-8 -*-
"""
test_sync_date_range.py
=======================
Pruebas unitarias para la sincronizacion manual de documenteme por rango de
fechas (contingencia): validacion pura del rango y delegacion al refresh.

Ejecutar con:
python -m pytest qp_supplier_front/tests/test_sync_date_range.py -v
"""
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import qp_supplier_front.uses_cases.documents.sync_all_whitelist as saw
from qp_supplier_front.uses_cases.documents.date_range import (
    MAX_RANGE_DAYS,
    validate_date_range,
)


def _iso(value):
    return value.strftime("%Y-%m-%d")


class TestValidateDateRange(unittest.TestCase):

    def setUp(self):
        self.today = date(2026, 11, 21)

    def test_rango_inclusivo_de_90_dias_es_valido(self):
        start = date(2026, 1, 1)
        end = date(2026, 3, 31)  # 31 + 28 + 31 = 90 dias inclusivos
        result = validate_date_range(_iso(start), _iso(end), today=self.today)
        self.assertTrue(result["ok"])
        self.assertIsNone(result["error"])
        self.assertEqual(result["nvfac_fini"], "01/01/2026")
        self.assertEqual(result["nvfac_ffin"], "31/03/2026")

    def test_rango_de_91_dias_es_invalido(self):
        result = validate_date_range(
            "2026-01-01", "2026-04-01", today=self.today)
        self.assertFalse(result["ok"])
        self.assertIn("90", result["error"])
        self.assertIsNone(result["nvfac_fini"])
        self.assertIsNone(result["nvfac_ffin"])

    def test_fin_no_puede_superar_hoy(self):
        end = self.today + timedelta(days=1)
        result = validate_date_range(
            _iso(self.today), _iso(end), today=self.today)
        self.assertFalse(result["ok"])
        self.assertIn("hoy", result["error"])

    def test_inicio_no_puede_ser_mayor_que_fin(self):
        result = validate_date_range(
            "2026-11-20", "2026-11-10", today=self.today)
        self.assertFalse(result["ok"])
        self.assertIn("mayor", result["error"])

    def test_fechas_requeridas(self):
        self.assertFalse(
            validate_date_range(None, "2026-11-21", today=self.today)["ok"])
        self.assertFalse(
            validate_date_range("2026-11-21", "", today=self.today)["ok"])

    def test_formato_invalido(self):
        result = validate_date_range(
            "21/11/2026", "2026-11-21", today=self.today)
        self.assertFalse(result["ok"])
        self.assertIn("formato", result["error"].lower())

    def test_acepta_objetos_date(self):
        result = validate_date_range(
            date(2026, 11, 1), date(2026, 11, 21), today=self.today)
        self.assertTrue(result["ok"])
        self.assertEqual(result["nvfac_fini"], "01/11/2026")
        self.assertEqual(result["nvfac_ffin"], "21/11/2026")

    def test_maximo_por_defecto_es_90(self):
        self.assertEqual(MAX_RANGE_DAYS, 90)


class TestSyncByDateRangeEndpoint(unittest.TestCase):

    def setUp(self):
        self.frappe = MagicMock()
        self.today = date.today()
        self.start = self.today - timedelta(days=10)

        self.patch_frappe = patch.object(saw, "frappe", self.frappe)
        self.patch_refresh = patch.object(saw, "refresh_documents")
        self.patch_frappe.start()
        self.refresh = self.patch_refresh.start()
        self.addCleanup(self.patch_frappe.stop)
        self.addCleanup(self.patch_refresh.stop)

    def test_delega_en_refresh_documents_con_rango(self):
        self.refresh.return_value = {"success": True, "created_count": 3}
        result = saw.sync_by_date_range(_iso(self.start), _iso(self.today))
        self.refresh.assert_called_once_with(
            nvfac_esta="T",
            nvfac_fini=self.start.strftime("%d/%m/%Y"),
            nvfac_ffin=self.today.strftime("%d/%m/%Y"),
            allow_fetch=True,
        )
        self.assertEqual(result["created_count"], 3)

    def test_exige_rol_system_manager(self):
        self.refresh.return_value = {"success": True}
        saw.sync_by_date_range(_iso(self.start), _iso(self.today))
        self.frappe.only_for.assert_called_once_with("System Manager")

    def test_rango_invalido_no_delega(self):
        end = self.today + timedelta(days=1)
        result = saw.sync_by_date_range(_iso(self.today), _iso(end))
        self.assertFalse(result["success"])
        self.assertTrue(result["error"])
        self.refresh.assert_not_called()

    def test_rango_mayor_a_90_dias_no_delega(self):
        start = self.today - timedelta(days=MAX_RANGE_DAYS)
        result = saw.sync_by_date_range(_iso(start), _iso(self.today))
        self.assertFalse(result["success"])
        self.refresh.assert_not_called()
