# -*- coding: utf-8 -*-
"""
test_bank_resolver_unit.py
==========================
Pruebas unitarias para services/bank_resolver.py.
Completamente aisladas de la base de datos y de Frappe usando mocks de sys.modules.

Ejecutar con: python3 -m unittest qp_supplier_front/tests/test_bank_resolver_unit.py -v
"""
import sys
from unittest.mock import MagicMock, patch

# Mock del modulo frappe antes de importar bank_resolver
mock_frappe = MagicMock()
sys.modules['frappe'] = mock_frappe

import unittest

# Importar el resolver y el normalizador después del mock
from qp_supplier_front.services.bank_resolver import resolve_bank_name
from qp_supplier_front.services.bank_normalizer import normalize


class TestBankResolverUnit(unittest.TestCase):

    def setUp(self):
        # Resetear los mocks de frappe en cada prueba
        mock_frappe.reset_mock()
        
        # Catálogo de bancos por defecto
        self.catalog = [
            {"name": "DAVIVIENDA", "bank_name": "DAVIVIENDA"},
            {"name": "AV VILLAS", "bank_name": "AV VILLAS"},
            {"name": "BBVA", "bank_name": "BBVA"},
            {"name": "BANCO COLOMBIA", "bank_name": "BANCO COLOMBIA"}
        ]
        mock_frappe.get_all.return_value = self.catalog
        
        # Por defecto, qp_SP_BankNameVariant no existe en los tests básicos
        # y db.exists retorna False para el doctype de variantes.
        def exists_mock(doctype, name=None):
            if doctype == "DocType" and name == "qp_SP_BankNameVariant":
                return False
            # Si se busca la existencia de la PK en Nivel 1
            if doctype == "Bank" and name:
                return any(b["name"] == name for b in self.catalog)
            return False
            
        mock_frappe.db.exists.side_effect = exists_mock
        mock_frappe.db.get_value.return_value = None

    def test_exact_match_nivel_1(self):
        # "DAVIVIENDA" existe exactamente en la PK
        result = resolve_bank_name("DAVIVIENDA")
        self.assertEqual(result, "DAVIVIENDA")

    def test_exact_match_normalized_nivel_2(self):
        # "davivienda" en minúsculas y sin acentos
        result = resolve_bank_name("davivienda")
        self.assertEqual(result, "DAVIVIENDA")

    def test_strip_prefijo_con_espacio_nivel_3b(self):
        # "BANCO DAVIVIENDA" -> strip -> "davivienda" -> exact match en catálogo
        result = resolve_bank_name("BANCO DAVIVIENDA")
        self.assertEqual(result, "DAVIVIENDA")

    def test_strip_prefijo_sin_espacio_nivel_3b(self):
        # "BANCODAVIVIENDA" -> strip -> "davivienda" -> exact match en catálogo
        result = resolve_bank_name("BANCODAVIVIENDA")
        self.assertEqual(result, "DAVIVIENDA")

    def test_banco_av_villas_entrada_con_prefijo_nivel_3b(self):
        """BANCO AV VILLAS → strip candidato → 'av villas' → match con AV VILLAS del catálogo"""
        result = resolve_bank_name("BANCO AV VILLAS")
        self.assertEqual(result, "AV VILLAS")

    def test_av_villas_entrada_sin_prefijo_strip_catalogo_nivel_3b(self):
        """AV VILLAS → sin strip candidato → strip catálogo 'BANCO AV VILLAS'→'av villas' → match"""
        self.catalog = [{"name": "BANCO AV VILLAS", "bank_name": "BANCO AV VILLAS"}]
        mock_frappe.get_all.return_value = self.catalog
        
        def exists_mock(doctype, name=None):
            if doctype == "DocType" and name == "qp_SP_BankNameVariant":
                return False
            if doctype == "Bank" and name:
                return any(b["name"] == name for b in self.catalog)
            return False
        mock_frappe.db.exists.side_effect = exists_mock
        
        result = resolve_bank_name("AV VILLAS")
        self.assertEqual(result, "BANCO AV VILLAS")

    def test_bbva_variantes_nivel_3b(self):
        # "banco bbva" -> strip -> "bbva" -> exact match
        result = resolve_bank_name("banco bbva")
        self.assertEqual(result, "BBVA")

    def test_sufijos_societarios_exacto_nivel_2(self):
        # "BANCO COLOMBIA S.A." -> normalize -> "banco colombia" -> exact match normalized
        result = resolve_bank_name("BANCO COLOMBIA S.A.")
        self.assertEqual(result, "BANCO COLOMBIA")

    def test_fallback_nivel_4(self):
        # Banco desconocido que no tiene similitud suficiente con ninguno
        result = resolve_bank_name("BANCO TOTALMENTE DESCONOCIDO")
        self.assertEqual(result, "BANCO TOTALMENTE DESCONOCIDO")

    def test_nivel_0_diccionario_variantes(self):
        # Habilitar el doctype de variantes
        def exists_mock(doctype, name=None):
            if doctype == "DocType" and name == "qp_SP_BankNameVariant":
                return True
            if doctype == "Bank" and name:
                return any(b["name"] == name for b in self.catalog)
            return False
        mock_frappe.db.exists.side_effect = exists_mock
        
        # Configurar retorno para la variante
        mock_frappe.db.get_value.return_value = "AV VILLAS"
        
        # Llamar con la variante cruda
        result = resolve_bank_name("BANCO COMERCIAL AV VILLAS")
        self.assertEqual(result, "AV VILLAS")
        
        # Verificar llamada a db.get_value con los parámetros correctos
        mock_frappe.db.get_value.assert_called_with(
            "qp_SP_BankNameVariant",
            {"raw_variant": "BANCO COMERCIAL AV VILLAS"},
            "canonical_bank"
        )


if __name__ == "__main__":
    unittest.main()
