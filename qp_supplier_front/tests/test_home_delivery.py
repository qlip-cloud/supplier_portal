# -*- coding: utf-8 -*-
"""Nucleo puro de las facturas de home delivery (sin frappe)."""
import unittest

from qp_supplier_front.uses_cases.documenteme.home_delivery import (
    HOME_DELIVERY_COMMENT,
    HOME_DELIVERY_MARK,
    build_home_delivery_line,
    is_home_delivery,
)


def _detail(qty, unit, subtotal=None):
    line = {"nvdet_tcan": qty, "nvdet_valo": unit}
    if subtotal is not None:
        line["nvdet_stot"] = subtotal
    return line


class TestHomeDeliveryDetection(unittest.TestCase):

    def test_marcador_case_insensitive(self):
        doc = {"nvfac_orde": "  ENTREGAPACIENTE009 "}
        self.assertTrue(is_home_delivery(doc))

    def test_oc_normal_no_es_home_delivery(self):
        self.assertFalse(is_home_delivery({"nvfac_orde": "OC-123"}))

    def test_sin_oc_no_es_home_delivery(self):
        self.assertFalse(is_home_delivery({}))
        self.assertFalse(is_home_delivery(None))

    def test_comentario_configurado(self):
        self.assertEqual(HOME_DELIVERY_COMMENT, "Factura de home delivery")
        self.assertEqual(HOME_DELIVERY_MARK, "entregapaciente009")


class TestBuildHomeDeliveryLine(unittest.TestCase):

    def test_acumula_cantidad_y_subtotal(self):
        lines = [
            _detail(2, 100, 200),
            _detail(3, 50, 150),
        ]
        line = build_home_delivery_line(lines, "HD-ITEM")
        self.assertEqual(line["item_code"], "HD-ITEM")
        self.assertEqual(line["qty"], 5)
        self.assertEqual(line["rate"], 70)
        self.assertEqual(line["receiving_no"], "")
        self.assertEqual(line["order_no"], "")

    def test_subtotal_con_fallback_a_cantidad_por_valor(self):
        line = build_home_delivery_line([_detail(4, 25)], "HD-ITEM")
        self.assertEqual(line["qty"], 4)
        self.assertEqual(line["rate"], 25)

    def test_sin_producto_configurado(self):
        self.assertIsNone(build_home_delivery_line([_detail(1, 10)], ""))

    def test_sin_lineas_de_detalle(self):
        self.assertIsNone(build_home_delivery_line([], "HD-ITEM"))

    def test_lineas_sin_cantidad_ni_valor(self):
        self.assertIsNone(build_home_delivery_line([_detail(0, 0)], "HD-ITEM"))


if __name__ == "__main__":
    unittest.main()
