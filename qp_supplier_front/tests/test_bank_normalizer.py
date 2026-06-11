# -*- coding: utf-8 -*-
"""
test_bank_normalizer.py
========================
Pruebas unitarias para services/bank_normalizer.py

Completamente aisladas de Frappe y de la base de datos.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_bank_normalizer.py -v
"""
import unittest
from qp_supplier_front.services.bank_normalizer import (
    normalize,
    strip_bank_prefix,
    similarity,
    FUZZY_THRESHOLD,
    FUZZY_STRIP_THRESHOLD,
    _MIN_STRIP_RESULT_LEN,
)


# ---------------------------------------------------------------------------
# Tests: normalize()
# ---------------------------------------------------------------------------
class TestNormalize(unittest.TestCase):

    def test_convierte_a_minusculas(self):
        self.assertEqual(normalize("BANCO DAVIVIENDA"), "banco davivienda")

    def test_elimina_tildes_espanol(self):
        self.assertEqual(normalize("Bogotá"), "bogota")
        self.assertEqual(normalize("Àv Vìllas"), "av villas")
        self.assertEqual(normalize("Ñoño"), "nono")

    def test_elimina_espacios_extremos(self):
        self.assertEqual(normalize("  DAVIVIENDA  "), "davivienda")
        self.assertEqual(normalize("\tBancolombia\n"), "bancolombia")

    def test_no_elimina_prefijos(self):
        """normalize NO debe quitar prefijos; eso es responsabilidad de strip_bank_prefix."""
        self.assertEqual(normalize("BANCO DAVIVIENDA"), "banco davivienda")
        self.assertEqual(normalize("Bank Of America"), "bank of america")
        self.assertEqual(normalize("Banque de France"), "banque de france")

    def test_nombre_ya_normalizado(self):
        self.assertEqual(normalize("davivienda"), "davivienda")

    def test_nombre_con_numeros(self):
        self.assertEqual(normalize("BANCO 2000"), "banco 2000")


# ---------------------------------------------------------------------------
# Tests: strip_bank_prefix()
# ---------------------------------------------------------------------------
class TestStripBankPrefix(unittest.TestCase):

    # --- Prefijos en español ---
    def test_strip_banco(self):
        self.assertEqual(strip_bank_prefix("banco davivienda"), "davivienda")

    def test_strip_banco_de(self):
        self.assertEqual(strip_bank_prefix("banco de bogota"), "bogota")

    def test_strip_banco_del(self):
        self.assertEqual(strip_bank_prefix("banco del estado"), "estado")

    def test_strip_banco_de_la(self):
        self.assertEqual(strip_bank_prefix("banco de la republica"), "republica")

    def test_strip_banco_av_villas(self):
        """Caso de prueba central del reporte."""
        self.assertEqual(strip_bank_prefix("banco av villas"), "av villas")

    # --- Prefijos en inglés ---
    def test_strip_bank_of(self):
        result = strip_bank_prefix("bank of america")
        # "america" tiene 7 chars ≥ _MIN_STRIP_RESULT_LEN → retorna el resultado
        self.assertEqual(result, "america")

    def test_strip_bank_of_the(self):
        self.assertEqual(strip_bank_prefix("bank of the west"), "west")

    def test_strip_bank(self):
        self.assertEqual(strip_bank_prefix("bank nordea"), "nordea")

    # --- Prefijos en francés ---
    def test_strip_banque_de(self):
        self.assertEqual(strip_bank_prefix("banque de france"), "france")

    def test_strip_banque_du(self):
        self.assertEqual(strip_bank_prefix("banque du leman"), "leman")

    # --- Sin prefijo → None ---
    def test_sin_prefijo_retorna_none(self):
        self.assertIsNone(strip_bank_prefix("davivienda"))
        self.assertIsNone(strip_bank_prefix("av villas"))
        self.assertIsNone(strip_bank_prefix("bancolombia"))  # "banco" es prefijo pero "lombia" es el resto

    def test_resultado_demasiado_corto_retorna_none(self):
        """Si el resultado tras el strip tiene < _MIN_STRIP_RESULT_LEN chars → None."""
        # "banco ab" → "ab" (2 chars) → None
        self.assertIsNone(strip_bank_prefix("banco ab"))
        # "bank xy" → "xy" (2 chars) → None
        self.assertIsNone(strip_bank_prefix("bank xy"))

    def test_nombre_vacio_retorna_none(self):
        self.assertIsNone(strip_bank_prefix("banco "))  # solo hay espacio → stripped = "" → None

    # --- Verificación del umbral mínimo ---
    def test_resultado_en_umbral_minimo(self):
        """Un resultado de exactamente _MIN_STRIP_RESULT_LEN chars es válido."""
        # "banco abc" → "abc" (3 chars = _MIN_STRIP_RESULT_LEN) → válido
        result = strip_bank_prefix("banco abc")
        self.assertEqual(result, "abc")


# ---------------------------------------------------------------------------
# Tests: similarity()
# ---------------------------------------------------------------------------
class TestSimilarity(unittest.TestCase):

    def test_cadenas_identicas(self):
        self.assertAlmostEqual(similarity("davivienda", "davivienda"), 1.0)
        self.assertAlmostEqual(similarity("av villas", "av villas"), 1.0)

    def test_bancos_totalmente_distintos(self):
        score = similarity("davivienda", "bancolombia")
        self.assertLess(score, FUZZY_THRESHOLD)

    def test_error_tipografico_leve(self):
        """Un error tipográfico leve debe superar el umbral base."""
        score = similarity("daviviemda", "davivienda")
        self.assertGreater(score, FUZZY_THRESHOLD)

    def test_diferencia_de_case_no_afecta(self):
        """Los inputs ya vienen normalizados (lowercase), este test documenta la expectativa."""
        score = similarity("davivienda", "davivienda")
        self.assertAlmostEqual(score, 1.0)

    def test_nombre_con_prefijo_vs_sin_prefijo(self):
        """
        'banco davivienda' vs 'davivienda' — similitud baja en el path directo.
        Este caso se resuelve en Level 3b (con strip), no en Level 3a.
        """
        score = similarity("banco davivienda", "davivienda")
        self.assertLess(score, FUZZY_THRESHOLD)

    def test_strip_result_vs_doctype(self):
        """
        Simula el flujo Level 3b:
        strip('banco av villas') = 'av villas' → compare con 'av villas' del doctype.
        """
        stripped = strip_bank_prefix("banco av villas")
        score = similarity(stripped, "av villas")
        self.assertGreaterEqual(score, FUZZY_STRIP_THRESHOLD)

    def test_strip_bank_of_america_no_match_falso(self):
        """
        'bank of america' → strip → 'america'.
        Comparado con 'bank of america' (nombre completo del doctype) → score bajo.
        El match correcto ocurre en Level 3a (sin strip).
        """
        stripped = strip_bank_prefix("bank of america")
        score_vs_full = similarity(stripped, "bank of america")
        self.assertLess(score_vs_full, FUZZY_STRIP_THRESHOLD)

    def test_constantes_de_umbral(self):
        """FUZZY_STRIP_THRESHOLD debe ser más estricto que FUZZY_THRESHOLD."""
        self.assertGreater(FUZZY_STRIP_THRESHOLD, FUZZY_THRESHOLD)


if __name__ == "__main__":
    unittest.main()
