# -*- coding: utf-8 -*-
"""
test_notification_state.py
==========================
Nucleo puro del estado de notificacion documenteme (nvfac_ueve).

Ejecutar:
  env/bin/python -m pytest qp_supplier_front/tests/test_notification_state.py -q
"""

import unittest

from qp_supplier_front.uses_cases.documenteme.notification_state import (
    is_final,
    is_known,
    is_pending,
    normalize,
    resolve_state,
    resolve_ueve,
    start_code,
)


class TestNormalize(unittest.TestCase):

    def test_vacios(self):
        self.assertEqual(normalize(None), "")
        self.assertEqual(normalize(""), "")
        self.assertEqual(normalize("   "), "")

    def test_espacios_y_tipos(self):
        self.assertEqual(normalize(" 030 "), "030")
        self.assertEqual(normalize(32), "32")


class TestClassification(unittest.TestCase):

    def test_pendientes(self):
        for value in (None, "", "030", "032", " 032 "):
            self.assertTrue(is_pending(value), value)

    def test_finales(self):
        for value in ("031", "033"):
            self.assertTrue(is_final(value), value)
            self.assertFalse(is_pending(value), value)

    def test_pendientes_no_son_finales(self):
        for value in (None, "", "030", "032"):
            self.assertFalse(is_final(value), value)

    def test_desconocido_no_es_conocido(self):
        self.assertFalse(is_known("034"))
        self.assertFalse(is_pending("034"))
        self.assertFalse(is_final("034"))
        for value in ("030", "031", "032", "033"):
            self.assertTrue(is_known(value), value)


class TestResolveState(unittest.TestCase):

    def test_origen_final_estado_manda(self):
        self.assertEqual(resolve_state("BCC", "A", None), "A")
        self.assertEqual(resolve_state("PA", "R", None), "R")
        self.assertEqual(resolve_state("BCC", "A", "030"), "A")

    def test_ueve_final_define_estado(self):
        self.assertEqual(resolve_state("BCC", "E", "033"), "A")
        self.assertEqual(resolve_state("PA", "E", "031"), "R")
        self.assertEqual(resolve_state("A", "E", "031"), "R")

    def test_intermedio_respeta_avanzado(self):
        for state in ("SO", "SR", "PSA", "BCC", "PA", "A", "R"):
            self.assertEqual(resolve_state(state, "E", "030"), state)
            self.assertEqual(resolve_state(state, "E", "032"), state)

    def test_intermedio_actualiza_analisis(self):
        self.assertEqual(resolve_state("V", "E", "030"), "E")
        self.assertEqual(resolve_state("E", "V", "032"), "V")
        self.assertEqual(resolve_state(None, "E", None), "E")

    def test_estado_local_final_no_baja_con_origen_intermedio(self):
        self.assertEqual(resolve_state("A", "E", None), "A")
        self.assertEqual(resolve_state("R", "E", "030"), "R")

    def test_advanced_states_inyectable(self):
        self.assertEqual(
            resolve_state("SO", "E", "030", advanced_states=("BCC",)), "E")


class TestResolveUeve(unittest.TestCase):

    def test_origen_manda_si_no_degrada_final_local(self):
        self.assertEqual(resolve_ueve("", "030"), "030")
        self.assertEqual(resolve_ueve("030", "032"), "032")
        self.assertEqual(resolve_ueve("032", "033"), "033")
        self.assertEqual(resolve_ueve("030", ""), "")

    def test_final_local_no_baja(self):
        self.assertEqual(resolve_ueve("033", "032"), "033")
        self.assertEqual(resolve_ueve("031", None), "031")
        self.assertEqual(resolve_ueve("033", "031"), "031")


class TestStartCode(unittest.TestCase):

    def test_aprobacion(self):
        self.assertEqual(start_code("A", None), "030")
        self.assertEqual(start_code("A", ""), "030")
        self.assertEqual(start_code("A", "030"), "032")
        self.assertEqual(start_code("A", "032"), "033")

    def test_rechazo(self):
        self.assertEqual(start_code("R", None), "030")
        self.assertEqual(start_code("R", "030"), "032")
        self.assertEqual(start_code("R", "032"), "031")

    def test_final_no_programa_eventos(self):
        self.assertIsNone(start_code("A", "033"))
        self.assertIsNone(start_code("A", "031"))
        self.assertIsNone(start_code("R", "031"))
        self.assertIsNone(start_code("R", "033"))

    def test_desconocido_arranca_secuencia_completa(self):
        self.assertEqual(start_code("A", "034"), "030")
        self.assertEqual(start_code("R", " 999 "), "030")


if __name__ == "__main__":
    unittest.main()
