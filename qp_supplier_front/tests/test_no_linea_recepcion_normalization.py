# -*- coding: utf-8 -*-
"""Regresion de NoLineaRecepcion en el builder BC compartido.

S1: con recepcion se conserva el idx del Purchase Receipt Item (puede
    repetirse entre recepciones distintas).
S2: sin recepcion se asigna (posicion + 1) * 10000, nunca "" ni el idx de
    origen (delivery, OC sin recibo, cuenta de cobro).
S3: NoRecepcion y NoPedido no cambian.
S4: el builder GP no se toca.
S5: la linea unica de collection tambien sale "10000".
"""

import unittest

from qp_supplier_front.uses_cases.collection_invoices.mapping import (
    build_single_line,
)
from qp_supplier_front.uses_cases.documenteme.approve import (
    _build_invoice,
    _line_recepcion_number,
    build_gp_invoice,
    build_payload,
    make_invoice_builder,
)


def _doc(**kwargs):
    doc = {
        "nvfac_fech": "2026-01-02",
        "nvpro_ndoc": "900",
        "nvfac_nume": "F1",
        "nvfac_orde": "OC1",
        "nvfac_cufe": "",
        "nvfac_stot": 100,
    }
    doc.update(kwargs)
    return doc


def _line(**kwargs):
    line = {
        "item_code": "I1",
        "qty": 1,
        "rate": 100,
        "idx": 0,
        "receiving_no": "",
        "order_no": "",
    }
    line.update(kwargs)
    return line


class TestNoLineaRecepcionNormalization(unittest.TestCase):
    # S1 -----------------------------------------------------------------
    def test_s1_recepcion_conserva_idx_del_item(self):
        invoice = _build_invoice(
            _doc(),
            [_line(idx=2, receiving_no="R1", order_no="OC1")],
            "WH",
        )
        line = invoice["vendorInvoiceLine"][0]
        self.assertEqual(line["NoLineaRecepcion"], "2")
        self.assertEqual(line["NoRecepcion"], "R1")
        self.assertEqual(line["NoPedido"], "OC1")

    def test_s1_idx_se_repite_entre_recepciones(self):
        invoice = _build_invoice(
            _doc(),
            [
                _line(idx=10000, receiving_no="R1", order_no="OC1"),
                _line(idx=10000, receiving_no="R2", order_no="OC2",
                      item_code="I2"),
            ],
            "WH",
        )
        self.assertEqual(
            [l["NoLineaRecepcion"] for l in invoice["vendorInvoiceLine"]],
            ["10000", "10000"],
        )

    # S2 -----------------------------------------------------------------
    def test_s2_sin_recepcion_usa_consecutivo_por_posicion(self):
        invoice = _build_invoice(
            _doc(),
            [
                _line(idx=0),
                _line(idx=5, order_no="OC9", item_code="I2"),
                _line(idx=7, item_code="I3"),
            ],
            "",
        )
        lines = invoice["vendorInvoiceLine"]
        self.assertEqual(
            [l["NoLineaRecepcion"] for l in lines],
            ["10000", "20000", "30000"],
        )
        self.assertEqual([l["NoRecepcion"] for l in lines], ["", "", ""])

    def test_s2_ignora_idx_de_origen_sin_recepcion(self):
        self.assertEqual(
            _line_recepcion_number({"receiving_no": "", "idx": 5}, 0), 10000
        )
        self.assertEqual(
            _line_recepcion_number({"receiving_no": "", "idx": 0}, 1), 20000
        )

    def test_s2_helper_con_recepcion_es_idx_y_nunca_vacio(self):
        self.assertEqual(
            _line_recepcion_number({"receiving_no": "R1", "idx": 10000}, 0),
            10000,
        )
        self.assertEqual(
            _line_recepcion_number({"receiving_no": "R2", "idx": 10000}, 1),
            10000,
        )
        self.assertNotEqual(
            _line_recepcion_number({"receiving_no": "", "idx": 0}, 0), ""
        )

    # S3 -----------------------------------------------------------------
    def test_s3_no_recepcion_y_no_pedido_sin_cambios(self):
        invoice = _build_invoice(
            _doc(),
            [
                _line(idx=2, receiving_no="R1", order_no="OC1"),
                _line(idx=0),
                _line(idx=9, order_no="OC2", item_code="I2"),
            ],
            "WH",
        )
        self.assertEqual(
            [(l["NoRecepcion"], l["NoPedido"])
             for l in invoice["vendorInvoiceLine"]],
            [("R1", "OC1"), ("", ""), ("", "OC2")],
        )

    # S4 -----------------------------------------------------------------
    def test_s4_gp_no_se_modifica(self):
        gp = build_gp_invoice(
            _doc(),
            [_line(idx=4, receiving_no="", order_no="OC1")],
            "WH",
            tipo_factura_doc=2,
        )
        line = gp["vendorInvoiceLine"][0]
        self.assertEqual(line["noLineaRecepcion"], 4)
        self.assertEqual(line["noRecepcion"], "OC1")
        self.assertEqual(line["noPedido"], "")

    # S5 -----------------------------------------------------------------
    def test_s5_collection_linea_unica_es_10000(self):
        def get_lines(_doc_arg):
            return [build_single_line(
                {"item_code": "POITEM", "idx": 3, "uom": "UN"}, 550, "OC1"
            )], ""

        payload = build_payload(
            [_doc()],
            get_lines,
            lambda po: "",
            build_invoice_fn=make_invoice_builder("collection"),
        )
        line = payload[0]["vendorInvoiceLine"][0]
        self.assertEqual(line["NoLineaRecepcion"], "10000")
        self.assertEqual(line["NoRecepcion"], "")
        self.assertEqual(line["NoPedido"], "OC1")
        self.assertEqual(line["NoProducto"], "POITEM")
        self.assertEqual(line["Precio"], 550.0)


if __name__ == "__main__":
    unittest.main()
