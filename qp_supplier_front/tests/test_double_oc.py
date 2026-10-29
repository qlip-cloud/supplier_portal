# -*- coding: utf-8 -*-
"""
test_double_oc.py
=================
Pruebas del soporte de varias ordenes de compra en una factura documenteme
(`nvfac_orde` con OC separadas por coma).

Ejecutar con:
python -m pytest qp_supplier_front/tests/test_double_oc.py -q
"""
import sys
import unittest
from unittest.mock import MagicMock, patch

from qp_supplier_front.services.enrich_document_detail import (
    enrich_document_detail,
)
from qp_supplier_front.uses_cases.documenteme.approve import (
    _allocate_registrables,
    _build_invoice,
)
from qp_supplier_front.uses_cases.documenteme.purchase_orders import (
    first_purchase_order,
    header_purchase_order,
    is_multiple_purchase_orders,
    parse_purchase_orders,
)


class TestPurchaseOrderParser(unittest.TestCase):

    def test_limpia_y_deduplica(self):
        self.assertEqual(
            parse_purchase_orders(" OC1, OC2 ,, OC1,  "),
            ["OC1", "OC2"],
        )

    def test_vacio_o_none(self):
        self.assertEqual(parse_purchase_orders(None), [])
        self.assertEqual(parse_purchase_orders("  , "), [])

    def test_acepta_lista(self):
        self.assertEqual(parse_purchase_orders(["OC1", " OC2 "]), ["OC1", "OC2"])

    def test_header_vacio_con_varias_oc(self):
        self.assertEqual(header_purchase_order("OC1, OC2"), "")
        self.assertEqual(header_purchase_order("OC1"), "OC1")
        self.assertEqual(first_purchase_order("OC1, OC2"), "OC1")
        self.assertTrue(is_multiple_purchase_orders("OC1,OC2"))
        self.assertFalse(is_multiple_purchase_orders("OC1"))


class TestMultiOcAllocation(unittest.TestCase):

    def _doc(self):
        return {
            "name": "DOC1",
            "nvfac_nume": "FAC1",
            "nvfac_orde": "OC1, OC2",
            "nvfac_stot": 1000,
            "nvfac_esta": "E",
            "nvfac_conv": "2",
            "nvtip_docu": "F",
        }

    def _bank(self, order):
        return {
            "OC1": [{"name": "R1", "amount": 600, "qp_invoice": None}],
            "OC2": [{"name": "R2", "amount": 400, "qp_invoice": None}],
        }.get(order, [])

    def test_pool_compartido_cubre_la_factura(self):
        valid, errors, allocation = _allocate_registrables(
            [self._doc()],
            lambda order: True,
            self._bank,
            0.01,
            po_supplier_match_fn=lambda doc: True,
        )

        self.assertEqual([doc["name"] for doc in valid], ["DOC1"])
        self.assertEqual(errors, [])
        self.assertEqual(
            sorted(receipt["name"] for receipt in allocation["DOC1"]),
            ["R1", "R2"],
        )

    def test_una_oc_invalida_usa_solo_las_validas(self):
        self._bank = lambda order: {
            "OC1": [{"name": "R1", "amount": 1000, "qp_invoice": None}],
            "OC2": [{"name": "R2", "amount": 400, "qp_invoice": None}],
        }.get(order, [])

        valid, errors, allocation = _allocate_registrables(
            [self._doc()],
            lambda order: order == "OC1",
            self._bank,
            0.01,
            po_supplier_match_fn=lambda doc: True,
        )

        self.assertEqual([doc["name"] for doc in valid], ["DOC1"])
        self.assertEqual(
            [receipt["name"] for receipt in allocation["DOC1"]], ["R1"])


class TestMultiOcPayloadLines(unittest.TestCase):

    def test_cada_linea_conserva_la_oc_de_su_recibo(self):
        from qp_supplier_front.resources.documenteme import _approve_base as base

        frappe_mock = MagicMock()

        def _get_all(doctype, filters=None, **kwargs):
            if doctype == "Purchase Receipt":
                return [
                    {"name": "R1", "qp_supplier_oc": "OC1"},
                    {"name": "R2", "qp_supplier_oc": "OC2"},
                ]
            return [
                {"parent": "R1", "item_code": "I1", "qty": 1, "rate": 100,
                 "idx": 1, "uom": "UN"},
                {"parent": "R2", "item_code": "I2", "qty": 1, "rate": 200,
                 "idx": 1, "uom": "UN"},
            ]

        frappe_mock.get_all.side_effect = _get_all
        with patch.object(base, "frappe", frappe_mock):
            lines = base.get_lines_from_receipts("OC1, OC2")

        self.assertEqual([line["order_no"] for line in lines], ["OC1", "OC2"])


class TestMultiOcHeader(unittest.TestCase):

    def _doc(self, nvfac_orde):
        return {
            "nvfac_fech": "2026-01-01",
            "nvfac_nume": "FAC1",
            "nvpro_ndoc": "9001",
            "nvfac_orde": nvfac_orde,
        }

    def test_pedido_proveedor_vacio_con_varias_oc(self):
        invoice = _build_invoice(self._doc("OC1, OC2"), [], "")
        self.assertEqual(invoice["NoPedidoProveedor"], "")

    def test_pedido_proveedor_conserva_oc_unica(self):
        invoice = _build_invoice(self._doc("OC1"), [], "")
        self.assertEqual(invoice["NoPedidoProveedor"], "OC1")

    def test_linea_recepcion_por_recibo_y_repetible(self):
        lines = [
            {"item_code": "I1", "qty": 1, "rate": 100, "idx": 10000,
             "receiving_no": "R1", "order_no": "OC1"},
            {"item_code": "I2", "qty": 1, "rate": 200, "idx": 10000,
             "receiving_no": "R2", "order_no": "OC2"},
        ]
        invoice = _build_invoice(self._doc("OC1, OC2"), lines, "")
        payload_lines = invoice["vendorInvoiceLine"]
        self.assertEqual(
            [line["NoLineaRecepcion"] for line in payload_lines],
            ["10000", "10000"],
        )
        self.assertEqual(
            [line["NoRecepcion"] for line in payload_lines],
            ["R1", "R2"],
        )
        self.assertEqual(
            [line["NoPedido"] for line in payload_lines],
            ["OC1", "OC2"],
        )


class _DoubleOcRefs(object):

    def __init__(self):
        self.claims = {}

    def po_exists(self, order):
        return True

    def po_belongs_to_supplier(self, order, tax_id):
        return True

    def po_items(self, order):
        return [{
            "item_code": "ITEM-" + order, "uom": "UN", "qty": 1,
            "qp_unit_cost": 500, "qp_extd_cost": 500,
        }]

    def receipts_for(self, order, qp_invoice=None):
        rows = [{
            "name": "R-" + order,
            "supplier_delivery_note": "RECIBO " + order,
            "posting_date": "2026-01-01",
            "total": 500,
        }]
        if qp_invoice is not None:
            return [row for row in rows
                    if self.claims.get(row["name"]) == qp_invoice]
        return rows

    def receipt_bank_for(self, order):
        return [{
            "name": "R-" + order, "amount": 500, "date": "2026-01-01",
            "qp_invoice": None,
        }]

    def bank_for_invoice(self, order, invoice_number):
        return [{
            "name": "R-" + order, "amount": 500, "date": "2026-01-01",
            "qp_invoice": None, "claimed_by_me": False, "selectable": True,
        }]

    def has_claimed_receipts(self, invoice_number):
        return False

    def receipt_items_for(self, names):
        return [{
            "parent": name, "item_code": "ITEM-" + name, "uom": "UN",
            "qty": 1, "rate": 500, "amount": 500,
        } for name in names]


class TestMultiOcEnrich(unittest.TestCase):

    def _doc(self, state="E"):
        return {
            "name": "DOC1",
            "nvfac_nume": "FAC1",
            "nvfac_orde": "OC1, OC2",
            "nvfac_totp": 1000,
            "nvfac_stot": 1000,
            "nvfac_esta": state,
            "nvpro_ndoc": "9001",
        }

    def _run(self, document, refs):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = []
        with patch.dict(sys.modules, {"frappe": frappe_mock}):
            enrich_document_detail(document, references=refs)
        return document

    def test_agrupa_productos_y_recibos_por_oc(self):
        document = self._run(self._doc(), _DoubleOcRefs())

        self.assertEqual(document["ordenes_compra"], ["OC1", "OC2"])
        self.assertEqual(
            [group["numero"] for group in document["ordenes_compra_detalle"]],
            ["OC1", "OC2"],
        )
        self.assertEqual(
            [group["numero"] for group in document["recepciones_por_oc"]],
            ["OC1", "OC2"],
        )
        self.assertEqual(
            [row["oc"] for row in document["banco_recepciones"]],
            ["OC1", "OC2"],
        )
        self.assertEqual(
            [row["oc"] for row in document["recepciones_detalle"]],
            ["OC1", "OC2"],
        )
        self.assertEqual(
            [group["numero"]
             for group in document["recepciones_detalle_por_oc"]],
            ["OC1", "OC2"],
        )

    def test_pool_compartido_promueve_a_v(self):
        document = self._run(self._doc(), _DoubleOcRefs())
        self.assertEqual(document["nvfac_esta"], "V")


if __name__ == "__main__":
    unittest.main()
