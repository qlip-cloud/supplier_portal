# -*- coding: utf-8 -*-
"""
test_documenteme_detail_limits.py
=================================
Pruebas del render del detalle de una factura documenteme con muchas OC o
muchas recepciones (modo resumen + detalle completo en modal).

Aisladas de la base de datos: frappe se inyecta como mock y las referencias de
compras se inyectan con un doble.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

from qp_supplier_front.services.enrich_document_detail import (
    INLINE_OC_LIMIT,
    INLINE_RECEIPT_LIMIT,
    enrich_document_detail,
)


def _order_names(count):
    return ["OC%03d" % index for index in range(1, count + 1)]


def _po_item(unit_cost=100):
    return {
        "item_code": "SH00086",
        "uom": "UN",
        "qty": 1,
        "qp_unit_cost": unit_cost,
        "qp_extd_cost": unit_cost,
    }


def _receipt(name, total, order, qp_invoice=None):
    return {
        "name": name,
        "supplier_delivery_note": name,
        "posting_date": "2026-01-01",
        "total": total,
        "qp_invoice": qp_invoice,
        "qp_supplier_oc": order,
    }


class _BatchRefs(object):
    """Adaptador fake con metodos batch (camino de facturas grandes)."""

    def __init__(self, orders, items=None, receipts=None):
        self.orders = list(orders)
        self.items = items or {}
        self.receipts = receipts or []
        self.calls = {
            "po_items": 0,
            "receipts_for": 0,
            "bank_for_invoice": 0,
            "receipt_items_for": 0,
        }
        self.batch_calls = {
            "po_belongs_to_supplier_many": 0,
            "po_items_many": 0,
            "receipts_for_many": 0,
            "bank_for_invoice_many": 0,
        }

    def po_exists(self, order):
        return order in self.orders

    def po_belongs_to_supplier(self, order, tax_id):
        return order in self.orders

    def po_belongs_to_supplier_many(self, orders, tax_id):
        self.batch_calls["po_belongs_to_supplier_many"] += 1
        return [order for order in orders if order in self.orders]

    def po_items(self, order):
        self.calls["po_items"] += 1
        return self.items.get(order, [])

    def po_items_many(self, orders):
        self.batch_calls["po_items_many"] += 1
        return dict(
            (order, self.items.get(order, []))
            for order in orders if order in self.orders
        )

    def receipts_for(self, order, qp_invoice=None):
        self.calls["receipts_for"] += 1
        return self._filter(order, qp_invoice)

    def receipts_for_many(self, orders, qp_invoice=None):
        self.batch_calls["receipts_for_many"] += 1
        rows = []
        for order in orders:
            rows.extend(self._filter(order, qp_invoice))
        return rows

    def _filter(self, order, qp_invoice=None):
        rows = []
        for receipt in self.receipts:
            if receipt.get("qp_supplier_oc") != order:
                continue
            if qp_invoice is not None and receipt.get("qp_invoice") != qp_invoice:
                continue
            row = dict(receipt)
            row["oc"] = order
            rows.append(row)
        return rows

    def bank_for_invoice(self, order, invoice_number):
        self.calls["bank_for_invoice"] += 1
        return self._bank([order], invoice_number)

    def bank_for_invoice_many(self, orders, invoice_number):
        self.batch_calls["bank_for_invoice_many"] += 1
        return self._bank(orders, invoice_number)

    def _bank(self, orders, invoice_number):
        rows = []
        for order in orders:
            for receipt in self.receipts:
                if receipt.get("qp_supplier_oc") != order:
                    continue
                owner = receipt.get("qp_invoice")
                if owner and owner != invoice_number:
                    continue
                rows.append({
                    "name": receipt.get("name"),
                    "amount": receipt.get("total") or 0,
                    "date": receipt.get("posting_date"),
                    "qp_invoice": owner,
                    "claimed_by_me": owner == invoice_number,
                    "selectable": True,
                    "oc": order,
                })
        return rows

    def receipt_bank_for(self, purchase_order_number):
        return [
            {
                "name": receipt.get("name"),
                "amount": receipt.get("total") or 0,
                "date": receipt.get("posting_date"),
                "qp_invoice": receipt.get("qp_invoice"),
            }
            for receipt in self.receipts
        ]

    def receipt_items_for(self, receipt_names):
        self.calls["receipt_items_for"] += 1
        return []


class _NoBatchRefs(object):
    """Adaptador fake SIN metodos batch (camino de respaldo por OC)."""

    def __init__(self, orders):
        self.orders = list(orders)
        self.belongs_calls = 0

    def po_exists(self, order):
        return order in self.orders

    def po_belongs_to_supplier(self, order, tax_id):
        self.belongs_calls += 1
        return order in self.orders

    def po_items(self, order):
        return []

    def receipts_for(self, order, qp_invoice=None):
        return []

    def bank_for_invoice(self, order, invoice_number):
        return []

    def receipt_bank_for(self, purchase_order_number):
        return []

    def receipt_items_for(self, receipt_names):
        return []


class TestDetailLimits(unittest.TestCase):

    def _document(self, orders, invoice="FAC-1", state="V"):
        return {
            "name": "DOC1",
            "nvfac_nume": invoice,
            "nvfac_orde": ", ".join(orders),
            "nvfac_stot": 1000,
            "nvfac_esta": state,
            "nvpro_ndoc": "9001",
        }

    def _run(self, document, refs, include_products=None):
        frappe_mock = MagicMock()
        frappe_mock.get_all.return_value = []
        frappe_mock.db.exists.return_value = True
        with patch.dict(sys.modules, {"frappe": frappe_mock}):
            enrich_document_detail(
                document, references=refs, include_products=include_products)
        return document

    def test_muchas_oc_modo_resumen_sin_productos(self):
        orders = _order_names(65)
        refs = _BatchRefs(
            orders,
            items=dict((order, [_po_item()]) for order in orders),
        )

        document = self._run(self._document(orders), refs)

        self.assertTrue(document["detail_limited"])
        self.assertEqual(document["orders_total"], 65)
        self.assertEqual(len(document["ordenes_compra_detalle"]), 65)
        self.assertTrue(all(
            group["productos"] == []
            for group in document["ordenes_compra_detalle"]
        ))
        self.assertEqual(document["productos_orden_compra"], [])
        # La validacion de OC y la lectura de recibos van por batch.
        self.assertEqual(refs.batch_calls["po_belongs_to_supplier_many"], 1)
        self.assertEqual(refs.calls["po_items"], 0)
        self.assertEqual(refs.calls["receipt_items_for"], 0)

    def test_forzar_detalle_completo_trae_productos(self):
        orders = _order_names(65)
        refs = _BatchRefs(
            orders,
            items=dict((order, [_po_item()]) for order in orders),
        )

        document = self._run(
            self._document(orders), refs, include_products=True)

        self.assertFalse(document["detail_limited"])
        self.assertTrue(document["ordenes_compra_detalle"][0]["productos"])
        self.assertTrue(document["productos_orden_compra"])
        self.assertEqual(refs.calls["po_items"], 0)
        self.assertEqual(refs.batch_calls["po_items_many"], 1)

    def test_pocas_oc_muchos_recibos_modo_resumen(self):
        orders = _order_names(2)
        receipts = []
        for index in range(INLINE_RECEIPT_LIMIT + 1):
            order = orders[index % 2]
            receipts.append(
                _receipt("REC%02d" % index, 100, order)
            )
        refs = _BatchRefs(orders, receipts=receipts)

        document = self._run(self._document(orders), refs)

        self.assertTrue(document["detail_limited"])
        self.assertEqual(document["receipts_total"], INLINE_RECEIPT_LIMIT + 1)
        self.assertEqual(refs.calls["receipt_items_for"], 0)
        self.assertTrue(all(
            group["productos"] == []
            for group in document["ordenes_compra_detalle"]
        ))

    def test_caso_normal_inline_con_productos(self):
        orders = _order_names(2)
        receipts = [_receipt("REC1", 600, orders[0])]
        refs = _BatchRefs(
            orders,
            items=dict((order, [_po_item()]) for order in orders),
            receipts=receipts,
        )

        document = self._run(self._document(orders), refs)

        self.assertFalse(document["detail_limited"])
        self.assertEqual(document["orders_total"], 2)
        self.assertEqual(document["receipts_total"], 1)
        self.assertTrue(document["ordenes_compra_detalle"][0]["productos"])
        self.assertEqual(refs.calls["po_items"], 2)
        self.assertEqual(refs.batch_calls["po_belongs_to_supplier_many"], 0)

    def test_totales_libres_y_reclamados(self):
        orders = _order_names(2)
        receipts = [
            _receipt("REC1", 600, orders[0]),
            _receipt("REC2", 400, orders[1], qp_invoice="FAC-1"),
            _receipt("REC3", 300, orders[0], qp_invoice="OTRA"),
        ]
        refs = _BatchRefs(orders, receipts=receipts)

        document = self._run(self._document(orders), refs)

        self.assertEqual(document["receipts_total"], 3)
        # REC3 esta tomado por otra factura: no es libre ni reclamado.
        self.assertEqual(document["receipts_free_count"], 1)
        self.assertEqual(document["receipts_free_total"], 600)
        self.assertEqual(document["receipts_claimed_count"], 1)
        self.assertEqual(document["receipts_claimed_total"], 400)

    def test_respaldo_por_oc_sin_metodos_batch(self):
        orders = _order_names(5)
        refs = _NoBatchRefs(orders)

        document = self._run(self._document(orders), refs)

        self.assertTrue(document["detail_limited"])
        self.assertEqual(document["orders_total"], 5)
        self.assertEqual(refs.belongs_calls, 5)


if __name__ == "__main__":
    unittest.main()
