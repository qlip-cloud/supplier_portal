# -*- coding: utf-8 -*-
"""
test_user_display.py
====================
Pruebas unitarias para services/user_display.py.

Regla: si el usuario no tiene apellido (full_name de una sola palabra), se
muestra su correo/identificador para no mostrar un nombre incompleto.
Ejecutar con: python -m pytest qp_supplier_front/tests/test_user_display.py -v
"""
import unittest

from qp_supplier_front.services.user_display import resolve_user_display_name


class TestResolveUserDisplayName(unittest.TestCase):

    def test_devuelve_nombre_cuando_tiene_apellido(self):
        self.assertEqual(
            resolve_user_display_name("Ana Perez", "ana@example.com"),
            "Ana Perez",
        )

    def test_devuelve_correo_cuando_solo_hay_un_nombre(self):
        self.assertEqual(
            resolve_user_display_name("johana", "johana@example.com"),
            "johana@example.com",
        )

    def test_devuelve_correo_cuando_full_name_es_vacio_o_none(self):
        self.assertEqual(resolve_user_display_name("", "u@example.com"), "u@example.com")
        self.assertEqual(resolve_user_display_name(None, "u@example.com"), "u@example.com")
        self.assertEqual(resolve_user_display_name("   ", "u@example.com"), "u@example.com")

    def test_normaliza_espacios_y_linea_base(self):
        self.assertEqual(
            resolve_user_display_name("  Ana   Perez  ", "ana@example.com"),
            "Ana Perez",
        )
        self.assertEqual(
            resolve_user_display_name("  johana  ", "johana@example.com"),
            "johana@example.com",
        )


if __name__ == "__main__":
    unittest.main()
